# Copyright (C) 2024 Pico Technology Ltd. See LICENSE file for terms.
from picosdk.psospa import psospa as ps
from picosdk.constants import PICO_STATUS, PICO_STATUS_LOOKUP
from picosdk.functions import adc2mVV2, mV2adcV2
from picosdk.PicoDeviceEnums import picoEnum as enums
from pycoviewlib.constants import (
    PV_DIR, chInputRanges, pCouplings, channelIDs, TriggerCondition,
    TriggerDirection, TriggerProperties,
)
from pycoviewlib.functions import log, detect_gate_open_closed, format_data
from ctypes import c_int16, c_int32, c_uint32, c_double, Array, byref
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime
from typing import Optional, Union
from itertools import islice


def plot_data(
        bufferChAmV: Array[c_int16],
        bufferChCmV: Array[c_int16],
        targets: list[str],
        gate: dict,
        time: np.ndarray,
        deltaT: float,
        timeIntervalns: float,
        title: str,
        ) -> None:
    buffersMin = min(min(bufferChAmV), min(bufferChCmV))
    buffersMax = max(max(bufferChAmV), max(bufferChCmV))
    yLowerLim = buffersMin * 1.2
    yUpperLim = buffersMax * 1.4

    fig, ax = plt.subplots(figsize=(10, 6), layout='tight')
    ax.grid()
    ax.set_xlabel('Time (ns)')
    ax.set_ylabel('Voltage (mV)')
    # ax.set_xlim(0, int(max(time)))
    # ax.set_ylim(yLowerLim, yUpperLim)

    """ Channel signals """
    ax.plot(time, bufferChAmV[:], color='blue', label='Channel A (gate)')
    ax.plot(time, bufferChCmV[:], color='green', label='Channel C (gate)')

    """ Bounds from gate """
    ax.plot(
        [gate[targets[0]]['open']['ns']] * 2,
        [gate[targets[0]]['open']['mV'], yLowerLim],
        linestyle='--', color='darkblue'
    )
    ax.plot(
        [gate[targets[0]]['closed']['ns']] * 2,
        [gate[targets[0]]['closed']['mV'], yLowerLim],
        linestyle='--', color='darkblue'
    )

    ax.plot(
        [gate[targets[1]]['open']['ns']] * 2,
        [gate[targets[1]]['open']['mV'], yLowerLim],
        linestyle='--', color='darkgreen'
    )
    ax.plot(
        [gate[targets[1]]['closed']['ns']] * 2,
        [gate[targets[1]]['closed']['mV'], yLowerLim],
        linestyle='--', color='darkgreen'
    )

    plt.fill_between(
        np.arange(
            gate[targets[0]]['open']['ns'],
            gate[targets[1]]['open']['ns'],
            timeIntervalns
        ),
        yLowerLim, yUpperLim,
        color='lightgrey', label=f'Delay\n{deltaT:.2f} ns'
    )

    """ Gate open and closed points """
    ax.plot(
        gate[targets[0]]['open']['ns'], gate[targets[0]]['open']['mV'],
        color='darkblue', marker='>',
        label=f"Gate A open\n{gate[targets[0]]['open']['ns']:.2f} ns"
    )
    ax.plot(
        gate[targets[0]]['closed']['ns'], gate[targets[0]]['closed']['mV'],
        color='darkblue', marker='<',
        label=f"Gate A closed\n{gate[targets[0]]['closed']['ns']:.2f} ns"
    )

    ax.plot(
        gate[targets[1]]['open']['ns'], gate[targets[1]]['open']['mV'],
        color='darkgreen', marker='>',
        label=f"Gate C open\n{gate[targets[1]]['open']['ns']:.2f} ns"
    )
    ax.plot(
        gate[targets[1]]['closed']['ns'], gate[targets[1]]['closed']['mV'],
        color='darkgreen', marker='<',
        label=f"Gate C closed\n{gate[targets[1]]['closed']['ns']:.2f} ns"
    )

    ax.set_title(title)
    plt.legend(loc='lower right')

    return fig


class TDC:
    def __init__(self, params: dict[str, Union[int, float, str]], probe: bool = False):
        self.params = params
        self.probe = probe
        self.timestamp: str = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        if not self.probe:
            self.datahandle: str = (f"{PV_DIR}/Data/{self.params['filename']}"
                                    f"_{self.timestamp}_data.{self.params['dformat']}")
            if self.params['log']:  # Creating loghandle if required
                self.loghandle: str = f"{self.params['filename']}_{self.timestamp}_tdc_log.txt"

        self.chandle = c_int16()
        self.status = {}

        self.resolution = enums.PICO_DEVICE_RESOLUTION['PICO_DR_8BIT']
        self.actionClearAll = enums.PICO_ACTION['PICO_CLEAR_ALL']
        self.actionAdd = enums.PICO_ACTION['PICO_ADD']
        self.actionClearAdd = self.actionClearAll | self.actionAdd
        self.downsampleModeRaw = enums.PICO_RATIO_MODE['PICO_RATIO_MODE_RAW']
        self.targets = params['target']
        self.nTargets = len(params['target'])
        self.analogOffset = {id: params[f'ch{id}analogOffset'] * 1000 for id in self.targets}
        self.chRange = {id: params[f'ch{id}range'] for id in self.targets}
        self.autoTrigms = params['autoTrigms']
        self.preTrigSamples = params['preTrigSamples']
        self.postTrigSamples = params['postTrigSamples']
        self.maxSamples = params['maxSamples']

        self.timebase = c_uint32()
        self.timeIntervalns = c_double()
        self.overvoltage = c_int16()  # Overvoltage (channel) flag
        self.rmaxSamples = c_int32(self.maxSamples)  # Actual number of samples collected
        self.maxADC = c_int16()  # Converted maxADC count

        self.count = 1  # Capture counter

    def __check_health(self, status: hex, stop: Optional[bool] = False) -> str | None:
        if status != PICO_STATUS['PICO_OK']:
            err = f'{PICO_STATUS_LOOKUP[status]}'
            if stop:
                self.status['stop'] = ps.psospaStop(self.chandle)
                if self.status['stop'] != PICO_STATUS['PICO_OK']:
                    err += f"+{PICO_STATUS_LOOKUP[self.status['stop']]}"
            ps.psospaCloseUnit(self.chandle)
            if self.params['log'] and not self.probe:
                log(self.loghandle, f"==> Job finished with error(s): {err}", time=True)
            return err

        return None

    def setup(self) -> str | None:
        err = []

        if self.nTargets != 2:
            return err.append(f'Expected 2 trigger targets, got {self.nTargets}')

        # Logging runtime parameters
        if self.params['log'] and not self.probe:
            log(self.loghandle, '==> Running acquisition with parameters:', time=True)
            col_width = max([len(k) for k in self.params.keys()])
            for key, value in self.params.items():
                log(self.loghandle, f'{key: <{col_width}} {value:}')

        if not self.probe:
            header = []
            if self.params['includeCounter']:
                header.append('n')
            header.append('deltaT (ns)')
            with open(self.datahandle, "a") as out:  # Creating data output file
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
                rangeMaxnV = chInputRanges[self.params[f'ch{name}range']] * 1000000
                rangeMinnV = -rangeMaxnV
                self.status[f'setCh{name}On'] = ps.psospaSetChannelOn(
                    self.chandle,
                    id,
                    pCouplings[self.params[f'ch{name}coupling']],
                    rangeMinnV,
                    rangeMaxnV,
                    0,  # range type = PICO_PROBE_RANGE_INFO['PICO_PROBE_NONE_NV']
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
        
        self.thresholdADC = {id: mV2adcV2(
            self.params['thresholdmV'] + self.analogOffset,
            self.gateChRangeMax,
            self.maxADC
        ) for id in self.targets}

        """ Setting up advanced trigger on target channels.
        ps.psospaSetTriggerChannelConditions(
            handle:       chandle
            conditions:   * TriggerCondition(
                              source:         (A=0, B=1, C=2, D=4)
                              trigger state:  PICO_CONDITION
                          )
            nConditions:  length of `directions` array
            action:       how to apply PICO_CONDITIONs to any existing conditions
        )
        ps.psospaSetTriggerChannelDirections(
            handle:       chandle
            directions:   * TriggerDirections(
                              channel:         (A=0, B=1, C=2, D=4)
                              direction:       PICO_THRESHOLD_DIRECTION
                              threshold mode:  (0=LEVEL, 1=WINDOW)
                          )
            nDirections:  length of `directions` array
        )
        ps.psospaSetTriggerChannelProperties(
            handle:       chandle
            properties:   * TriggerProperties(
                              thresholdUpper:   value in ADC counts
                              hysteresisUpper:  0
                              thresholdLower:   0
                              hysteresisLower:  0
                              channel:          (A=0, B=1, C=2, D=4)
                          )
            nProperties:  length of `properties` array
            wait for:     value in microseconds
        ) """
        conditions = (TriggerCondition * self.nTargets)()
        directions = (TriggerDirection * self.nTargets)()
        properties = (TriggerProperties * self.nTargets)()

        for idx, _ in enumerate(self.targets):
            conditions[idx].source = c_int32(idx)
            conditions[idx].condition = enums.PICO_TRIGGER_STATE['PICO_CONDITION_TRUE']

            directions[idx].channel = c_int32(idx)
            directions[idx].direction = enums.PICO_THRESHOLD_DIRECTION['PICO_FALLING']
            directions[idx].thresholdMode = enums.PICO_THRESHOLD_MODE['PICO_LEVEL']

            properties[idx].thresholdUpper = self.thresholdADC[idx]
            properties[idx].thresholdUpperHysteresis = 0
            properties[idx].thresholdLower = 0
            properties[idx].thresholdLowerHysteresis = 0
            properties[idx].channel = c_int32(idx)

        self.status['setTriggerChConditions'] = ps.psospaSetTriggerChannelConditions(
            self.chandle, byref(conditions), self.nTargets, self.actionClearAdd
        )
        err.append(self.__check_health(self.status['setTriggerChConditions']))

        self.status['setTriggerChannelDirections'] = ps.psospaSetTriggerChannelDirections(
            self.chandle, *directions, self.nTargets
        )
        err.append(self.__check_health(self.status['setTriggerChannelDirections']))

        self.status['setTriggerChProperties'] = ps.psospaSetTriggerChannelProperties(
            self.chandle, byref(properties), self.nTargets, self.autoTrigms * 1000
        )
        err.append(self.__check_health(self.status['setTriggerChProperties']))

        self.status['setTriggerDelay'] = ps.psospaSetTriggerDelay(
            self.chandle, self.params['delaySeconds'],
        )
        err.append(self.__check_health(self.status['setTriggerDelay']))

        """ Get minimum available timebase """
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

    def run(self) -> tuple[float | None, str | None]:
        err = []

        # Logging capture
        if self.params['log'] and not self.probe:
            to_be_logged = [dict(entry=f'==> Beginning capture no. {self.count}', time=True)]

        """ Run block capture """
        self.status['runBlock'] = ps.psospaRunBlock(
            self.chandle,
            self.preTrigSamples,
            self.postTrigSamples,
            self.timebase,
            None,                  # returned recovery time (milliseconds or NULL)
            0,                     # segment index
            None,                  # lpReady (using psospaIsReady instead)
            None                   # pParameter
        )
        err.append(self.__check_health(self.status['runBlock'], stop=True))

        """ Check for data collection to finish using psospaIsReady """
        ready = c_int16(0)
        check = c_int16(0)
        while ready.value == check.value:
            self.status['isReady'] = ps.ps6000IsReady(self.chandle, byref(ready))

        """ Set data buffers location for data collection """
        bufferAMax = (c_int16 * self.maxSamples)()
        bufferCMax = (c_int16 * self.maxSamples)()

        buffers = {'A': bufferAMax, 'C': bufferCMax}

        for idx, name in enumerate(self.targets):
            self.status[f'setDataBuffer{name}'] = ps.psospaSetDataBuffer(
                self.chandle,
                channelIDs.index(name),                              # source
                byref(buffers[name]),                                # pointer to gate buffer
                self.maxSamples,
                enums.PICO_DATA_TYPE['PICO_INT16_T'],
                0,                                                   # waveform (segment index)
                self.downsampleModeRaw,                              # downsample mode
                self.actionClearAdd if idx == 0 else self.actionAdd  # clear busy bufs and/or add new
            )
            err.append(self.__check_health(self.status[f'setDataBuffer{name}'], stop=True))

        """ Retrieve data from scope to buffers assigned above """
        self.status['getValues'] = ps.psospaGetValues(
            self.chandle,
            0,                        # start index
            byref(self.rmaxSamples),  # actual no. of samples retrieved (<= maxSamples)
            1,                        # downsample ratio
            self.downsampleModeRaw,   # downsample mode
            0,                        # memory segment index where data is stored
            byref(self.overvoltage)   # overvoltage (channel) flag
        )
        err.append(self.__check_health(self.status['getValues'], stop=True))

        """ Convert ADC counts data to mV """
        bufferChAmV = adc2mVV2(bufferAMax, self.chRange[self.targets[0]], self.maxADC)
        bufferChCmV = adc2mVV2(bufferCMax, self.chRange[self.targets[1]], self.maxADC)

        """ Removing the analog offset from data points """
        thresholdmV = {
            id: (self.thresholdADC * (self.chRange[id] / 1000000)) \
            / self.maxADC.value - self.analogOffset for id in self.targets
        }
        for i in range(self.rmaxSamples.value):
            bufferChAmV[i] -= self.analogOffset
            bufferChCmV[i] -= self.analogOffset

        """ Create time data """
        time = np.linspace(
            0,
            (self.rmaxSamples.value - 1) * self.timeIntervalns.value,
            self.rmaxSamples.value
        )

        """ Detect where the threshold was hit (both rising & falling edge) """
        gate: dict[str, dict[str, float | int]] = {id: {} for id in self.targets}
        for id, buffer in zip(self.targets, [bufferChAmV, bufferChCmV]):
            gate[id] = detect_gate_open_closed(
                buffer, time, thresholdmV[id], self.maxSamples, self.timeIntervalns.value
            )
        # Skip current acquisition if trigger timed out (all gates open at 0.0ns)
        if all([g['open']['ns'] == 0.0 for g in gate.values()]):
            if self.params['log'] and not self.probe:
                to_be_logged.append('Skipping (trigger timeout).')
            return None, [None]

        """ Calculating relevant data """
        data = []
        if self.params['includeCounter']:
            data.append(self.count)
        deltaT = gate[self.targets[1]]['open']['ns'] - gate[self.targets[0]]['open']['ns']
        data.append(deltaT)

        if self.params['log'] and not self.probe:
            to_be_logged.append('Ok!')
            for item in to_be_logged:
                if isinstance(item, dict):
                    log(self.loghandle, **item)
                else:
                    log(self.loghandle, item)

        """ Print data to file """
        if not self.probe:
            with open(self.datahandle, 'a') as out:
                out.write(format_data(data, self.params['dformat']))
        else:
            figure = plot_data(
                bufferChAmV, bufferChCmV, self.targets, gate, time, deltaT,
                self.timeIntervalns.value, f'TDC Probe {self.timestamp}'
            )
            return figure, err

        self.count += 1

        return deltaT, err

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
