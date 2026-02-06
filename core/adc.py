from ctypes import c_int16, c_int32, c_uint32, c_double, Array, byref
import numpy as np
from picosdk.psospa import psospa as ps
from picosdk.errors import PicoSDKCtypesError
from picosdk.constants import PICO_STATUS_LOOKUP
from picosdk.PicoDeviceEnums import picoEnum as enums
from pycoviewlib.functions import (
    detect_gate_open_closed, calculate_charge, log, key_from_value, format_data
)
from pycoviewlib.constants import PV_DIR, chInputRanges, couplings, pCouplings, channelIDs
import matplotlib.pyplot as plt
from picosdk.functions import adc2mVV2, mV2adcV2, assert_pico_ok
from datetime import datetime
from typing import Union
from itertools import islice


def plot_data(
        bufferGate: Array[c_int16],
        bufferSignal: Array[c_int16],
        gate: dict,
        time: np.ndarray,
        timeIntervalns: float,
        charge: float,
        peakToPeak: float,
        title: str,
        ) -> None:
    maxSignal = max(bufferSignal)
    yLowerLim = min(min(bufferGate), min(bufferSignal)) * 1.1
    yUpperLim = max(abs(max(bufferGate)), abs(maxSignal)) * 1.3

    fig, ax = plt.subplots(figsize=(10, 6), layout='tight')
    ax.grid()
    ax.set_ylim(yLowerLim, yUpperLim)
    ax.set_xlabel('Time (ns)')
    ax.set_ylabel('Voltage (mV)')

    """ Channel signals """
    ax.plot(time, bufferGate[:], color='blue', label='Channel A (gate)')
    ax.plot(time, bufferSignal[:], color='green', label='Channel C (detector signal)')

    """ Charge area + bounds from gate """
    fillY = bufferSignal[gate['open']['index']:gate['closed']['index']]
    fillX = np.linspace(gate['open']['ns'], gate['closed']['ns'], num=len(fillY))
    ax.fill_between(
        fillX, fillY, color='lightgrey', label=f'Total deposited charge\n{charge:.2f} pC'
        )
    ax.plot(
        [gate['open']['ns']] * 2, [gate['open']['mV'], maxSignal],
        linestyle='--', color='black'
        )
    ax.plot(
        [gate['closed']['ns']] * 2, [gate['closed']['mV'], maxSignal],
        linestyle='--', color='black'
        )

    """ Gate open and closed points """
    ax.plot(
        gate['open']['ns'], gate['open']['mV'],
        color="black", marker=">", label=f"Gate open\n{gate['open']['ns']:.2f} ns"
        )
    ax.plot(
        gate['closed']['ns'], gate['closed']['mV'],
        color="black", marker="<", label=f"Gate closed\n{gate['closed']['ns']:.2f} ns"
        )

    """ Amplitude and Peak-To-Peak """
    ax.annotate(
            '',
            xy=(time[bufferSignal.index(maxSignal)], maxSignal),
            xytext=(time[bufferSignal.index(maxSignal)], min(bufferSignal)),
            fontsize=12,
            arrowprops=dict(edgecolor='black', arrowstyle='<->', shrinkA=0, shrinkB=0)
            )
    ax.text(
            time[bufferSignal.index(maxSignal)] + 0.5,
            maxSignal - peakToPeak / 2, f'Peak-to-peak\n{peakToPeak:.2f} mV')

    ax.set_title(title)
    ax.legend(loc='lower right')

    return fig


class ADC:
    def __init__(self, params: dict[str, Union[int, float, str]], probe: bool = False):
        self.params = params
        self.probe = probe
        self.timestamp: str = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        if self.params['log']:  # Creating loghandle if required
            self.loghandle: str = f"{self.params['filename']}_{self.timestamp}_adc_log.txt"
        self.datahandle: str = f"{PV_DIR}/Data/{self.params['filename']}_{self.timestamp}_data.{self.params['dformat']}"

        self.chandle = c_int16()
        self.status = {}

        self.resolution = enums.PICO_DEVICE_RESOLUTION['PICO_DR_8BIT']
        self.delaySeconds = params['delaySeconds']
        self.targetChRange = params[f"ch{params['target']}range"]
        self.rangeMax = chInputRanges[params[f"ch{params['target']}range"]] * 1000000
        self.rangeMin = -self.rangeMax * 1000000
        self.rangeType = 0  # probes.PICO_PROBE_RANGE_INFO['PICO_PROBE_NONE_NV']
        self.analogOffset = params[f"ch{params['target']}analogOffset"]
        self.autoTrigms = params['autoTrigms']
        self.preTrigSamples = params['preTrigSamples']
        self.postTrigSamples = params['postTrigSamples']
        self.maxSamples = params['maxSamples']
        # self.timebase = list(timebases.values())[f"{params['timebase']}"]
        self.timebase = c_uint32()
        self.timeIntervalns = c_double()
        self.coupling = couplings[key_from_value(couplings, params[f"ch{params['target']}coupling"])][1]

        self.overvoltage = c_int16()  # Overvoltage (channel) flag
        self.cmaxSamples = c_int32(self.maxSamples)  # Converted type maxSamples
        self.maxADC = c_int16()

        self.count = 1  # Capture counter

    def __check_health(self, status: hex, stop: bool = False) -> str | None:
        try:
            assert_pico_ok(status)
        except PicoSDKCtypesError:
            if stop:
                self.status['stop'] = ps.psospaStop(self.chandle)
                self.__check_health(self.status['stop'])
            ps.psospaCloseUnit(self.chandle)
            return f'{PICO_STATUS_LOOKUP[status]}'
        return None

    def setup(self) -> list[str] | None:
        err = []

        """ Logging runtime parameters """
        if self.params['log'] and not self.probe:
            log(self.loghandle, '==> Running acquisition with parameters:', time=True)
            col_width = max([len(k) for k in self.params.keys()])
            for key, value in self.params.items():
                log(self.loghandle, f'{key: <{col_width}} {value:}')

        if not self.probe:
            header = []
            if self.params['includeCounter']:
                header.append('n')
            if self.params['includeAmplitude']:
                header.append('amplitude (mV)')
            if self.params['includePeakToPeak']:
                header.append('peak2peak (mV)')
            header.append('charge (pC)')
            with open(self.datahandle, 'a') as out:  # Creating data output file
                out.write(format_data(header, self.params['dformat']))

        """ Opening PicoScope connection: returns handle for future use in API functions """
        self.status['openUnit'] = ps.psospaOpenUnit(
            byref(self.chandle),
            None,                 # returned Pico serial (not needed)
            self.resolution,
            None                  # returned power info (not needed)
        )
        err.append(self.__check_health(self.status['openUnit']))

        """ Setting up channels according to `params`
        ps.psospaSetChannelOn(
            handle:     chandle
            id:         (A=0, B=1, C=2, D=3)
            coupling:   (AC1Mohm=0, DC1Mohm=1, DC50ohm=2)
            range:      see chInputRanges in pycoviewlib/constants.py
            offset:     analog offset (value in volts)
            bandwidth:  see pycoviewlib/constants.py
        )
        ps.psospaSetChannelOff(
            handle:     chandle
            id:         (A=0, B=1, C=2, D=3)
        ) """
        for id, name in enumerate(channelIDs):
            if self.params[f'ch{name}enabled']:
                self.params[f'ch{name}rangeMaxnv'] = chInputRanges[self.params[f'ch{name}range']] * 1000000
                self.params[f'ch{name}rangeMinnv'] = -self.params[f'ch{name}rangeMaxnv']
                self.status[f'setCh{name}On'] = ps.psospaSetChannelOn(
                    self.chandle,
                    id,
                    pCouplings[self.params[f'ch{name}coupling']],
                    self.params[f'ch{name}rangeMinnv'],
                    self.params[f'ch{name}rangeMaxnv'],
                    self.rangeType,
                    self.params[f'ch{name}analogOffset'],  # value in volts
                    self.params[f'ch{name}bandwidth']
                )
                err.append(self.__check_health(self.status[f'setCh{name}On']))
            else:
                self.status[f'setCh{name}Off'] = ps.psospaSetChannelOff(
                    self.chandle, id
                )
                err.append(self.__check_health(self.status[f'setCh{name}Off']))

        # Getting ADC limits, converting threshold to ADC
        self.status['getADCLimits'] = ps.psospaGetAdcLimits(
            self.chandle,
            self.resolution,
            None,               # minADC not needed
            byref(self.maxADC)
        )
        err.append(self.__check_health(self.status['getADCLimits']))
        
        self.thresholdADC = mV2adcV2(
            self.params['thresholdmV'] + self.analogOffset * 1000,
            self.rangeMax,
            self.maxADC
        )

        # Setting up simple trigger on target channel
        self.status['setSimpleTrigger'] = ps.psospaSetSimpleTrigger(
            self.chandle,
            1,                                          # enabled (yes=1, no=0)
            channelIDs.index(self.params['target']),
            self.thresholdADC,
            enums.PICO_THRESHOLD_DIRECTION['PICO_FALLING'],
            self.delaySeconds,
            self.autoTrigms * 1000                      # wait for (microseconds)
        )
        err.append(self.__check_health(self.status['setSimpleTrigger']))
 
        # Get timebase info & pre/post trigger samples to be collected
        enabledChFlags = sum([       # v~~~ Filtering only A, B, C, D flags
            flag for flag, id in zip(islice(enums.PICO_CHANNEL_FLAGS.values(), 4), channelIDs) \
            if self.params[f'ch{id}enabled']
        ])
        self.status['getMinTimebase'] = ps.psospaGetMinimumTimebaseStateless(
            self.chandle,
            enabledChFlags,             # flags ORed together (A=1, B=2, C=4, D=8)
            byref(self.timebase),       # returned shortest available timebase (ps)
            byref(self.timeIntervalns), # returned interval between samples (s)
            self.resolution             # PICO_DR_8BIT
        )
        err.append(self.__check_health(self.status['getMinTimebase']))

        self.timeIntervalns = c_double(self.timeIntervalns.value * 1000000000)  # to nanoseconds

        return err

    def run(self) -> tuple[float | None, list[str] | None] | plt.Figure:
        err = []

        """ Logging capture """
        if self.params['log'] and not self.probe:
            to_be_logged = [dict(entry=f'==> Beginning capture no. {self.count}', time=True)]

        """ Run block capture """
        self.status['runBlock'] = ps.psospaRunBlock(
            self.chandle,
            self.preTrigSamples,
            self.postTrigSamples,
            self.timebase,
            None,                   # returned recovery time (milliseconds or NULL)
            0,                      # segment index
            None,                   # lpReady (using psospaIsReady instead)
            None                    # pParameter
        )
        err.append(self.__check_health(self.status['runBlock'], stop=True))

        """ Check for data collection to finish using psospaIsReady """
        ready = c_int16(0)
        check = c_int16(0)
        while ready.value == check.value:
            ps.psospaIsReady(self.chandle, byref(ready))

        """ Create buffers ready for assigning pointers for data collection.
        'bufferXMin' are generally used for downsampling but in our case they're equal
        to bufferXMax as we don't need to downsample.
        """
        bufferAMax = (c_int16 * self.maxSamples)()
        bufferCMax = (c_int16 * self.maxSamples)()

        # Set data buffers location for data collection
        actionClearAll = enums.PICO_ACTION['PICO_CLEAR_ALL']
        actionAdd = enums.PICO_ACTION['PICO_ADD']
        actionClearAdd = actionClearAll | actionAdd
        downsampleModeRaw = enums.PICO_RATIO_MODE['PICO_RATIO_MODE_RAW']
        channelGate = channelIDs.index(self.params['target'])
        channelSignal = [
            channelIDs.index(id) for id in channelIDs \
            if self.params[f'ch{id}enabled'] and not id == self.params['target']
        ][0]

        self.status['setDataBufferGate'] = ps.psospaSetDataBuffer(
            self.chandle,
            channelGate,                           # source (channel A)
            byref(bufferAMax),                     # pointer to gate buffer
            self.maxSamples,
            enums.PICO_DATA_TYPE['PICO_INT16_T'],
            0,                                     # waveform (segment index)
            downsampleModeRaw,                     # downsample mode
            actionClearAdd                         # clear busy buffers then add new
        )
        err.append(self.__check_health(self.status['setDataBufferGate'], stop=True))

        self.status['setDataBufferSig'] = ps.psospaSetDataBuffer(
            self.chandle,
            channelSignal,                         # source (channel C)
            byref(bufferCMax),                     # pointer to signal buffer
            self.maxSamples,
            enums.PICO_DATA_TYPE['PICO_INT16_T'],
            0,                                     # waveform (segment index)
            downsampleModeRaw,                     # downsample mode
            actionAdd                              # add new buffer
        )
        err.append(self.__check_health(self.status['setDataBufferSig'], stop=True))

        """ Retrieve data from scope to buffers assigned above """
        self.status['getValues'] = ps.psospaGetValues(
            self.chandle,
            0,                        # start index
            byref(self.cmaxSamples),  # actual no. of samples retrieved (<= maxSamples)
            1,                        # downsample ratio
            downsampleModeRaw,        # downsample mode
            0,                        # memory segment index where data is stored
            byref(self.overvoltage)   # overvoltage (channel) flag
        )
        err.append(self.__check_health(self.status['getValues'], stop=True))

        """ Convert ADC counts data to mV """
        bufferChAmV = adc2mVV2(bufferAMax, self.rangeMax, self.maxADC)
        bufferChCmV = adc2mVV2(bufferCMax, self.rangeMax, self.maxADC)

        """ Removing the analog offset from data points """
        thresholdmV = (self.thresholdADC * chInputRanges[self.targetChRange]) \
            / self.maxADC.value - (self.analogOffset * 1000)
        for i in range(self.maxSamples):
            bufferChAmV[i] -= (self.analogOffset * 1000)
            bufferChCmV[i] -= (self.analogOffset * 1000)

        """ Create time data """
        time = np.linspace(
            0,
            (self.cmaxSamples.value - 1) * self.timeIntervalns.value,
            self.cmaxSamples.value
        )

        """ Detect where the threshold was hit (both falling & rising edge) """
        gate = detect_gate_open_closed(
            bufferChAmV, time, thresholdmV, self.maxSamples, self.timeIntervalns.value
        )
        # Skip current acquisition if trigger timed out
        if all([gopen['ns'] == 0.0 for gopen in gate.values()]):
            if self.params['log'] and not self.probe:
                to_be_logged.append('Skipping (trigger timeout).')
            return None, [None]
        # else:
        #   """ Logging threshold hits """
        #   if self.params['log'] and not self.probe:
        #       log(self.loghandle, f"gate on: {gate['open']['mV']:.2f}mV, \
        #           {gate['open']['ns']:.2f}ns @ {gate['open']['index']}",)
        #       log(self.loghandle, f"gate off: {gate['closed']['mV']:.2f}mV, \
        #           {gate['closed']['ns']:.2f}ns @ {gate['closed']['index']}")

        """ Calculating relevant data """
        data = []
        if self.params['includeCounter']:
            data.append(self.count)
        if self.params['includeAmplitude'] or self.probe:
            amplitude = abs(min(bufferChCmV))
            data.append(amplitude)
        if self.params['includePeakToPeak'] or self.probe:
            peakToPeak = abs(min(bufferChCmV)) - abs(max(bufferChCmV))
            data.append(peakToPeak)
        charge = calculate_charge(
                bufferChCmV, (gate['open']['index'], gate['closed']['index']),
                self.timeIntervalns.value, self.coupling
                )
        data.append(charge)

        """ Logging capture results """
        if self.params['log'] and not self.probe:
            to_be_logged.append('Ok!')
            for item in to_be_logged:
                if isinstance(item, dict):
                    log(self.loghandle, **item)
                else:
                    log(self.loghandle, item)

        # """ Logging capture results """
        # if self.params['log'] and not self.probe:
        #   if self.params['includeAmplitude']:
        #       log(self.loghandle, f'amplitude: {amplitude:.2f}mV')
        #   if self.params['includePeakToPeak']:
        #       log(self.loghandle, f'peak-to-peak: {peakToPeak:.2f}mV')
        #   log(self.loghandle, f'charge: {charge:.2f}pC')

        """ Print data to file """
        if not self.probe:
            with open(self.datahandle, 'a') as out:
                out.write(format_data(data, self.params['dformat']))
        else:
            figure = plot_data(
                bufferChAmV, bufferChCmV, gate, time, self.timeIntervalns,
                charge, peakToPeak, f'ADC Probe {self.timestamp}'
            )
            return figure, err

        self.count += 1

        return charge, err

    def stop(self) -> str | None:
        """ Stop acquisition & close unit """
        self.status['stop'] = ps.psospaStop(self.chandle)
        err = self.__check_health(self.status['stop'])
        ps.psospaCloseUnit(self.chandle)
        if err is not None:
            if self.params['log'] and not self.probe:
                log(self.loghandle, f'==> Job finished with error: {err}', time=True)
            return err

        """ Logging exit status & data location """
        if self.params['log'] and not self.probe:
            log(self.loghandle, '==> Job finished without errors. Data saved to:', time=True)
            log(self.loghandle, f'{self.datahandle}')

        return None
