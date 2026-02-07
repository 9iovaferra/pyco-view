"""
Copyright (C) 2019 Pico Technology Ltd.
tkSliderWidget Copyright (c) 2020, Mengxun Li
"""
import tkinter as tk
from tkinter.filedialog import asksaveasfilename
from tkinter.ttk import (
    Widget, Label, Frame, Labelframe, Entry, Checkbutton, Button, Spinbox,
    OptionMenu, Notebook, Scrollbar
)
try:
    from pyi_splash import close as pyi_splash_close  # Close splash screen when app has loaded
except ModuleNotFoundError:
    pass
from pycoviewlib.functions import parse_config, backup_config, key_from_value, get_timeinterval
from pycoviewlib.constants import (
    PV_DIR, channelIDs, dataFileTypes, modes, couplings, bandwidths, chInputRanges
)
import pycoviewlib.gui_resources as gui
from pycoviewlib.tkSliderWidget.tkSliderWidget import Slider
from core import adc, tdc, meantimer
from core.get_pico_info import pico_info
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from threading import Thread, Event
from queue import Queue
from os import system
# from datetime import datetime
from pathlib import Path
from typing import Union, Optional
from webbrowser import open_new


class App(tk.Tk):
    def __init__(self, *args, **kwargs):
        tk.Tk.__init__(self, *args, **kwargs)
        self.resizable(0, 0)
        self.after(0, self.hide())
        self.title('PycoView')
        dockIcon = tk.PhotoImage(file='pycoview.png')
        self.wm_iconphoto(False, dockIcon)
        self.protocol('WM_DELETE_WINDOW', self.delete_window)

        self.menu_bar = tk.Menu(self, relief='flat', bd=0)
        self.config(menu=self.menu_bar)
        self.file_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(menu=self.file_menu, label='File')
        self.file_menu.add_command(label='Open data folder', command=self.show_data_folder)
        # self.file_menu.add_separator()
        # self.file_menu.add_command(label='Generate config file', command=self.generate_config)
        self.help_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(menu=self.help_menu, label='Help')
        self.help_menu.add_command(label='About', command=self.open_about_window)

    def hide(self, target=None) -> None:
        """ Hide window until widgets are drawn to avoid visual glitch """
        if target is None:
            target = self
        self.attributes('-alpha', 0.0)

    def center(self, target=None) -> None:
        if target is None:
            target = self
        target.update_idletasks()
        screen_w = target.winfo_screenwidth()
        screen_h = target.winfo_screenheight()
        border_w = target.winfo_rootx() - target.winfo_x()
        title_h = target.winfo_rooty() - target.winfo_y()
        target_w = target.winfo_width() + 2 * border_w
        target_h = target.winfo_height() + title_h + border_w
        x = (screen_w - target_w) // 2
        y = (screen_h - target_h) // 2
        target.geometry(f'+{x}+{y}')
        target.attributes('-alpha', 1.0)

    def show_data_folder(self) -> None:
        datapath = Path(f'{PV_DIR}/Data')
        system(f'xdg-open {datapath}')

    def info_window(
            self,
            info: list[str],
            title='Error',
            subtitle='One or more error(s) occurred.'
            ) -> None:
        info_win = tk.Toplevel()
        info_win.resizable(0, 0)
        info_win.after(0, self.hide())
        info_win.title(title)
        frame = Frame(info_win, padding=(gui.WIDE_PAD, gui.WIDE_PAD, gui.WIDE_PAD, gui.WIDE_PAD))
        frame.grid(row=0, column=0, sticky='nesw')
        Label(
            frame, text=subtitle, anchor='nw'
        ).grid(row=0, column=0, pady=(0, gui.WIDE_PAD), sticky='nw')
        text = tk.Listbox(frame, font=('Segoe Ui', '10'), width=40, height=10)
        text.configure(exportselection=0, activestyle='none')  # This doesn't work?
        scrollb_v = Scrollbar(frame, command=text.yview, orient='vertical')
        scrollb_h = Scrollbar(frame, command=text.xview, orient='horizontal')
        text.configure(yscrollcommand=scrollb_v.set, xscrollcommand=scrollb_h.set)
        scrollb_v.grid(row=1, column=1, sticky='ns')
        scrollb_h.grid(row=2, column=0, sticky='ew')
        text.grid(row=1, column=0, sticky='nesw')
        for entry in info:
            text.insert(tk.END, entry)
        buttons_frame = Frame(frame, padding=(0, gui.THIN_PAD, 0, 0))
        buttons_frame.grid(row=3, column=0, columnspan=2, sticky='nse')
        help_button = Button(
            buttons_frame, text='Help', width=7,
            command=lambda: open_new(
                'https://www.picotech.com/download/manuals/picoscope-3000e-series-psospa-programmers-guide.pdf'
            )
        )
        close_button = Button(
            buttons_frame, text='Close', width=7,
            command=info_win.destroy
        )
        help_button.grid(row=0, column=0, padx=(0, gui.THIN_PAD), sticky='nse')
        close_button.grid(row=0, column=1, sticky='nse')
        self.center(target=info_win)

    def open_about_window(self) -> None:
        about = tk.Toplevel()
        about.geometry('250x180')
        about.resizable(0, 0)
        about.after(0, self.hide())
        about.title('About')
        title = Label(about, text='PycoView', font=18, anchor='center')
        title.pack(expand=1, fill='x')
        app_version = Label(about, text='v0.1', anchor='center')
        app_version.pack(expand=1, fill='x')
        link = Label(about, text='Github Repository', foreground='blue', cursor='hand2', anchor='center')
        link.pack(expand=1, fill='x')
        link.bind('<Button-1>', lambda _: open_new('https://github.com/9iovaferra/pyco-view'))
        self.center(target=about)

    def delete_window(self) -> None:
        self.quit()
        self.destroy()


class ChannelSettings():
    def __init__(self, parent: Notebook, name: str, col: int, row: int, target: Checkbutton = None):
        self.frame = gui.PVLabelframe(
            parent=parent, title=f'Channel {name}', size=(1, 9),
            col=col, row=row, padding=gui.lbf_asym_padding
        )
        self.target = target
        self.max_offset = chInputRanges[params[f'ch{name}range']]

        self.enabled_w = self.frame.add_checkbutton(
            id=f'ch{name}enabled',
            prompt='Enabled',
            on_off=(1, 0),
            default=params[f'ch{name}enabled'],
            padding={
                'padx': gui.lbf_contents_padding['padx'],
                'pady': (gui.THIN_PAD, 0)
            }
        )
        self.range_w = self.frame.add_combobox(
            id=f'ch{name}range',
            options=chInputRanges,
            default=chInputRanges[params[f'ch{name}range']],
            prompt='Range (±mV)'
        )
        self.range_w.bind(
            '<<ComboboxSelected>>', lambda _: self.__enforce_max_offset(name=name)
        )
        self.coupling_w = self.frame.add_combobox(
            id=f'ch{name}coupling',
            options=list(couplings.keys()),
            default=key_from_value(couplings, params[f'ch{name}coupling']),
            prompt='Coupling'
        )
        self.analogoffset_w = self.frame.add_spinbox(
            id=f'ch{name}analogOffset',
            from_to=(0, self.max_offset),
            step=1,
            default=int(params[f'ch{name}analogOffset'] * 1e3),
            prompt='Analogue offset (mV)'
        )
        self.bandwidth_w = self.frame.add_combobox(
            id=f'ch{name}bandwidth',
            options=list(bandwidths.keys()),
            default=key_from_value(bandwidths, params[f'ch{name}bandwidth']),
            prompt='Bandwidth'
        )
        self.frame.arrange()

        self.frame.children[f'ch{name}enabled'][0].configure(
            command=lambda: self.toggle_channel_state(settings[f'ch{name}enabled'].get())
        )
        self.toggle_channel_state(params[f'ch{name}enabled'])

    def __enforce_max_offset(self, name: str) -> None:
        self.max_offset = int(self.range_w.get())
        # Ensure current analogue offset value is within range & bind validation
        gui.assert_entry_ok(self.analogoffset_w, (0, self.max_offset))
        self.analogoffset_w.bind(
            '<FocusOut>',
            lambda _: gui.assert_entry_ok(self.analogoffset_w, (0, self.max_offset))
        )
    
    def toggle_channel_state(self, enabled: int) -> None:
        for w in list(self.frame.children.values())[1:] + [self.target]:
            toggle_widget_state(w[0], 'disabled' if not enabled else '!disabled')


class Histogram():
    def __init__(
            self,
            parent: Labelframe,
            xlim: list[int],
            bins: int,
            ylim: list[int] = None,
            mode: Optional[str] = '',
            ):
        self.parent = parent
        self.root = None
        self.mode = mode
        self.buffer = []
        self.follower = None
        self.fig, self.ax = plt.subplots(figsize=(6, 4.2), layout='tight')
        self.bins = bins
        self.xlim = xlim
        self.ylim = ylim if ylim is not None else [0, 15]
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.parent)
        self.canvas.get_tk_widget().grid(
            column=0, row=0, padx=gui.THIN_PAD, pady=gui.THIN_PAD, sticky='nesw'
        )
        self.stop_event = Event()
        self.stop_event.set()
        self.queue = Queue(maxsize=100)

    def create(
            self,
            bounds: tuple[int, int] = None,
            bins: int = None,
            widget_hook: tk.Widget = None
            ) -> None:
        """
        Generates or updates the histogram, if new bounds and/or bins values
        are provided. Ticks are adjusted to ensure readability.
        """
        self.ax.set_xlabel('Charge (pC)' if self.mode == 'adc' else 'Delay (ns)')
        self.ax.set_ylabel('Counts')

        if bounds is not None and bounds != self.xlim:
            self.xlim = bounds
            self.ax.set_xlim(bounds)
            update_setting(
                ['histBounds'],
                [f'{int(bounds[0])},{int(bounds[1])}'],
            )
        else:
            self.ax.set_xlim(self.xlim)

        if not self.ax.patches:  # Only update ylim if histogram is empty
            self.ax.set_ylim(self.ylim)
            yticks = range(0, int(self.ax.get_ylim()[1]) + 5, 5)
            self.ax.set_yticks(ticks=list(yticks), labels=[f'{lbl}' for lbl in yticks])

        if self.stop_event.is_set() and self.ax.patches:  # Readjust bins after run
            _ = [bar.remove() for bar in self.ax.patches]
            new_counts, new_bins = np.histogram(self.buffer, range=self.xlim, bins=self.bins)
            self.ax.stairs(new_counts, new_bins, fill=True, color=gui.HIST_COLOR, zorder=3)

        if (self.xlim[1] - self.xlim[0]) >= 200:
            xticks = range(int(self.xlim[0]), int(self.xlim[1]) + 20, 20)
        elif (self.xlim[1] - self.xlim[0]) in range(100, 200):
            xticks = range(int(self.xlim[0]), int(self.xlim[1]) + 10, 10)
        else:
            xticks = range(int(self.xlim[0]), int(self.xlim[1]) + 5, 5)

        self.ax.set_xticks(ticks=list(xticks), labels=[f'{lbl}' for lbl in xticks])
        self.ax.yaxis.grid(zorder=0)

        if bins is not None and bins != self.bins:
            self.bins = bins
            update_setting(['histBins'], [bins])

        if widget_hook is not None:
            widget_hook.state(['disabled'])

        self.canvas.draw()

    def save(self) -> None:
        figureSavePath = asksaveasfilename(
            initialdir=f'{PV_DIR}/Data',
            filetypes=[('PNG', '*.png'), ('PDF', '*.pdf')]
        )
        self.fig.savefig(figureSavePath)

    def start(self, root: tk.Tk, max_timeouts: int):
        """
        Creates follower thread, attempts to setup communication with PicoScope,
        exits if unsuccessful, starts thread otherwise
        """
        PV_STATUS.set(f'Starting {key_from_value(modes, self.mode)}...')
        self.root = root
        self.root.update_idletasks()
        self.cleanup()  # Scrape canvas & buffer if restarting
        self.follower = Thread(target=self.follow, args=[max_timeouts])

        match self.mode:
            case 'adc':
                self.applet = adc.ADC(params)
            case 'tdc':
                self.applet = tdc.TDC(params)
            case 'mntm':
                self.applet = meantimer.Meantimer(params)

        err = self.applet.setup()
        if not all([e is None for e in err]):
            PV_STATUS.set(f'(!) {", ".join([e for e in err if e is not None])}')
            return
        self.stop_event.clear()
        self.follower.start()
        self.root.protocol('WM_DELETE_WINDOW', self.kill)

    def follow(self, max_timeouts: int) -> None:
        """
        Gets data by running the applet.
        All tkinter commands must run in mainloop, so data is queued
        to `place_on_canvas()` which is outside of follower thread.
        """
        count = 1
        self.timeout = max_timeouts

        while not self.stop_event.is_set():
            if self.timeout == 0:
                PV_STATUS.set('Too many timeouts, please check your setup.')
                self.stop_event.set()
                err = self.applet.stop()
                if err is not None:
                    PV_STATUS.set(f'(!) {err}')
                break
            data, err = self.applet.run()
            if not all([e is None for e in err]):
                PV_STATUS.set(f"(!) {','.join([e for e in err if e is not None])}")
                self.stop_event.set()
                continue
            elif data is None:
                PV_STATUS.set(
                    f'Capture #{count}... skipping (trigger timeout {max_timeouts - self.timeout + 1})'
                    )
                self.timeout -= 1
                continue
            self.timeout = max_timeouts
            self.queue.put((data, count))
            self.place_on_canvas()
            count += 1

    def place_on_canvas(self) -> None:
        data, count = self.queue.get()
        self.buffer.append(data)

        if count % 5 == 0:  # Only update every 5 counts
            if self.ax.patches:
                _ = [bar.remove() for bar in self.ax.patches]
            counts, bins = np.histogram(self.buffer, range=self.xlim, bins=self.bins)
            self.ax.stairs(counts, bins, fill=True, color=gui.HIST_COLOR, zorder=3)

            yUpperLim = int(self.ax.get_ylim()[1])
            if np.max(counts) > yUpperLim * 0.95:
                if yUpperLim < 50:
                    yLimNudge = 5
                elif yUpperLim in range(50, 100):
                    yLimNudge = 10
                elif yUpperLim in range(100, 200):
                    yLimNudge = 20
                elif yUpperLim in range(200, 300):
                    yLimNudge = 25
                elif yUpperLim in range(300, 500):
                    yLimNudge = 50
                elif yUpperLim >= 500:
                    yLimNudge = 100
                self.ax.set_ylim(0, yUpperLim + yLimNudge)
                self.ax.set_yticks(
                    ticks=list(range(0, yUpperLim + 2 * yLimNudge, yLimNudge)),
                    labels=[f'{lbl}' for lbl in range(0, yUpperLim + 2 * yLimNudge, yLimNudge)]
                    )
            self.canvas.draw()

        if not self.stop_event.is_set():
            PV_STATUS.set(f'Capture #{count}')
        self.queue.task_done()

    def cleanup(self) -> None:
        if self.ax.patches:
            _ = [bar.remove() for bar in self.ax.patches]
            self.buffer = []
            self.ax.set_ylim(self.ylim)  # Reset ylim
            yticks = range(0, int(self.ax.get_ylim()[1]) + 5, 5)
            self.ax.set_yticks(ticks=list(yticks), labels=[f'{lbl}' for lbl in yticks])
            self.canvas.draw()

    def stop(self) -> None:
        if self.stop_event.is_set():
            PV_STATUS.set('No process to stop.')
            return
        PV_STATUS.set('Stopping...')
        self.root.update_idletasks()
        self.stop_event.set()
        if self.follower is not None:
            self.follower.join(timeout=0.1)
            self.follower = None
        err = self.applet.stop()
        PV_STATUS.set('Idle' if err is None and self.timeout != 0 else f'(!) {err}')

    def kill(self) -> None:
        self.stop()
        self.root.quit()
        self.root.destroy()


def get_pico_info(root: tk.Tk) -> None:
    err, info = pico_info()
    if not all([e is None for e in err]):
        root.info_window(info=list(dict.fromkeys(err)))
        PV_STATUS.set('Error!')
        return
    root.info_window(info=list(dict.fromkeys(info)), title='PicoScope Info', subtitle='PicoScope Info')


def probe_pico(root: tk.Tk, mode: str, max_timeouts: int) -> None:
    PV_STATUS.set('Probing PicoScope...')
    root.update_idletasks()

    match mode:
        case 'adc':
            applet = adc.ADC(params, probe=True)
        case 'tdc':
            applet = tdc.TDC(params, probe=True)
        case 'mntm':
            applet = meantimer.Meantimer(params, probe=True)
    err = applet.setup()
    if not all([e is None for e in err]):
        root.info_window(info=list(dict.fromkeys(err)))
        PV_STATUS.set('Error!')
        return

    figure = None
    timeout = max_timeouts
    while figure is None:
        if timeout == 0:
            PV_STATUS.set('Too many timeouts. Please check your setup.')
            root.update_idletasks()
            break
        figure, err = applet.run()
        if figure is None:
            PV_STATUS.set(
                f'Probing PicoScope... (trigger timeout {max_timeouts - timeout + 1})'
            )
            root.update_idletasks()
        timeout -= 1
    if not all([e is None for e in err]):
        root.info_window(info=list(dict.fromkeys(err)))
        PV_STATUS.set('Error!')
    err = applet.stop()

    if timeout != 0:
        if err is not None:
            PV_STATUS.set('Error!')
            root.info_window(info=[err])
            return

        PV_STATUS.set('Idle')
        probe_window = tk.Toplevel()
        probe_window.resizable(0, 0)
        probe_window.title('Probe')
        probe_canvas = FigureCanvasTkAgg(figure, master=probe_window)
        probe_canvas.get_tk_widget().grid(row=0, column=0, sticky='nesw')
        buttons_frame = Frame(probe_window, padding=(0, gui.THIN_PAD, 0, 0))
        buttons_frame.grid(row=1, column=0, pady=(0, gui.WIDE_PAD), sticky='nes')
        save_as_button = Button(
            buttons_frame, text='Save as...', width=9,
            command=lambda: saveas(figure)
        )
        close_button = Button(
            buttons_frame, text='Close', width=9,
            command=probe_window.destroy
        )
        save_as_button.grid(row=1, column=0, padx=(0, gui.THIN_PAD), sticky='nse')
        close_button.grid(row=1, column=1, padx=(0, gui.WIDE_PAD), sticky='nse')

    def saveas(fig: plt.Figure) -> None:
        figureSavePath = asksaveasfilename(
            initialdir=f'{PV_DIR}/Data',
            filetypes=[('PNG', '*.png'), ('PDF', '*.pdf')]
        )
        fig.savefig(figureSavePath)


def apply_changes(settings: dict, apply_btn: Button, ui_ch_labels: dict[str, Label]) -> None:
    """ Compares `settings` against `params`,
    sends updated values to `update_setting()` """
    keys: list[str] = []
    values: list[int | float | str] = []
    update: bool = False
    # Some settings require further processing before being saved to file
    special: dict[str, Union[int, float, str]] = {}
    for id in channelIDs:
        special[f'ch{id}range'] = chInputRanges.index(settings[f'ch{id}range'].get())
        special[f'ch{id}coupling'] = couplings[settings[f'ch{id}coupling'].get()][0]
        special[f'ch{id}analogOffset'] = settings[f'ch{id}analogOffset'].get() * 1e-3
        special[f'ch{id}bandwidth'] = bandwidths[settings[f'ch{id}bandwidth'].get()]

    # Iterate over merge of `settings` and `special`
    for k, v in (settings | special).items():
        new_value = v if k in special.keys() else v.get()
        if params[k] != new_value:
            keys.append(k)
            values.append(new_value)
            update = True

    if update:
        update_setting(keys=keys, new_values=values, ui_ch_labels=ui_ch_labels)

    apply_btn.state(['disabled'])


def update_setting(
        keys: list[str],
        new_values: list[Union[str, int, float]],
        ui_ch_labels: dict[str, Label] | None = None
        ) -> None:
    """
    Compares key-value pairs in `config.ini` to
    the same pairs given as input, overwrites file as needed
    """
    with open(f'{PV_DIR}/config.ini', 'r') as ini:
        lines = ini.readlines()
    for k, v in zip(keys, new_values):
        params[k] = v
        for i, line in enumerate(lines):
            if k in line:
                lines[i] = f'{k} = {v}\n'
                break
    with open(f'{PV_DIR}/config.ini', 'w') as ini:
        ini.writelines(lines)

    # Updating `Summary`
    if ui_ch_labels is not None:  # UI needs update only on `Apply` button click
        for id, color in zip(channelIDs, gui.CH_COLORS.values()):
            ui_textvar[f'ch{id}range'].set(f"±{chInputRanges[params[f'ch{id}range']]}")
            ui_textvar[f'ch{id}analogOffset'].set(int(params[f'ch{id}analogOffset'] * 1000))
            ui_textvar[f'ch{id}coupling'].set(key_from_value(couplings, params[f'ch{id}coupling']))
            ui_textvar[f'ch{id}bandwidth'].set(key_from_value(bandwidths, params[f'ch{id}bandwidth']))
            ui_textvar[f'ch{id}target'].set(u'\u25cF' if id in params['target'] else u'\u25cB')
            ui_textvar[f'ch{id}enabled']['bg'].set(color if params[f'ch{id}enabled'] else 'gray63'),
            ui_textvar[f'ch{id}enabled']['fg'].set('white' if params[f'ch{id}enabled'] else 'light gray')
            ui_ch_labels[id].configure(
                background=ui_textvar[f'ch{id}enabled']['bg'].get(),
                foreground=ui_textvar[f'ch{id}enabled']['fg'].get()
            )

        ui_textvar['thresholdmV'].set(f"{params['thresholdmV']:.0f} mV"),
        ui_textvar['delaySeconds'].set(f"{params['delaySeconds']} s"),
        ui_textvar['autoTrigms'].set(f"{params['autoTrigms']} ms"),
        ui_textvar['maxTimeouts'].set(f"{params['maxTimeouts']}"),
        ui_textvar['preTrigSamples'].set(f"{params['preTrigSamples']}"),
        ui_textvar['postTrigSamples'].set(f"{params['postTrigSamples']}"),


def on_mode_change(
        mode: str,
        hist: Optional[Histogram] = None,
        hook_widgets: Optional[list[Widget]] = None
        ) -> None:
    update_setting(['mode'], [mode])
    if hist is not None:
        hist.mode = mode
        hist.create()
    if hook_widgets is not None:
        for widget in hook_widgets:
            toggle_widget_state(widget, state='disabled' if mode != 'adc' else 'normal')


def toggle_widget_state(widget: Widget, state: str = 'normal') -> None:
    widget.configure(state=state)


def main() -> None:
    """ Main window """
    root: tk.Tk = App()
    root.tk.call('source', 'pycoviewlib/ttkAzure/azure.tcl')
    root.tk.call('set_theme', 'light')
    global PV_STATUS  # App status shown in the bottom left
    PV_STATUS = tk.StringVar(root, value='Idle')

    """ Reading runtime parameters from .ini file """
    global params  # dict[str, Union[int, float, str]]
    params = parse_config()
    backup_config()

    # TODO: Allow user to choose `Data` folder path
    try:
        pv_data_folder: Path = Path(f'{PV_DIR}/Data').expanduser()
        pv_data_folder.mkdir(exist_ok=True)
    except PermissionError:
        PV_STATUS.set('Error!')
        root.info_window(info=[f'Cannot write to {pv_data_folder}!'])

    global settings  # Stores Tkinter variables linked to widgets
    settings = {
        'filename': tk.StringVar(value=params['filename']),
        'dformat': tk.StringVar(value=params['dformat']),
        'target': tk.StringVar(value=''.join(params['target'])),
        'maxTimeouts': tk.IntVar(value=params['maxTimeouts']),
    }

    # 'ui_textvar' is a container of tkinter variable objects used to
    # update the UI as settings are changed
    global ui_textvar
    ui_textvar = {
        f'ch{id}{param}': None for id in channelIDs \
        for param in ['range', 'analogOffset', 'coupling', 'bandwidth', 'target']
    }
    for id, color in zip(channelIDs, gui.CH_COLORS.values()):
        ui_textvar[f'ch{id}range'] = tk.StringVar(value=f"±{chInputRanges[params[f'ch{id}range']]}")
        ui_textvar[f'ch{id}analogOffset'] = tk.IntVar(value=int(params[f'ch{id}analogOffset'] * 1000))
        ui_textvar[f'ch{id}coupling'] = tk.StringVar(value=key_from_value(couplings, params[f'ch{id}coupling']))
        ui_textvar[f'ch{id}bandwidth'] = tk.StringVar(value=key_from_value(bandwidths, params[f'ch{id}bandwidth']))
        ui_textvar[f'ch{id}target'] = tk.StringVar(value=u'\u25cF' if id in params['target'] else u'\u25cB')
        ui_textvar[f'ch{id}enabled'] = {
            'bg': tk.StringVar(value=color if params[f'ch{id}enabled'] else 'gray63'),
            'fg': tk.StringVar(value='white' if params[f'ch{id}enabled'] else 'light gray')
        }

    ui_textvar.update({
        'timebase': tk.StringVar(value=get_timeinterval(params['timebase'])),
        'thresholdmV': tk.StringVar(value=f"{params['thresholdmV']:.0f} mV"),
        'delaySeconds': tk.StringVar(value=f"{params['delaySeconds']} s"),
        'autoTrigms': tk.StringVar(value=f"{params['autoTrigms']} ms"),
        'maxTimeouts': tk.StringVar(value=f"{params['maxTimeouts']}"),
        'preTrigSamples': tk.StringVar(value=f"{params['preTrigSamples']}"),
        'postTrigSamples': tk.StringVar(value=f"{params['postTrigSamples']}"),
    })

    """ Top frame - contains `Mode` selector and `Filename` textbox """
    topFrame = Frame(root, padding=(gui.THIN_PAD, 0, gui.THIN_PAD, gui.THIN_PAD))
    topFrame.grid(column=0, row=0, padx=gui.WIDE_PAD, pady=(gui.WIDE_PAD, 0), sticky='new')
    topFrame.columnconfigure(2, weight=3)

    # Mode selector was moved *after* histogram creation because it needs Histogram instance
    # getInfo = Button(topFrame, text='Get Info', width=8, state=tk.DISABLED, command=lambda: get_pico_info(root=root))
    # getInfo.grid(column=2, row=0, padx=(gui.MED_PAD, 0), sticky='w')

    Label(topFrame, text='Filename:', anchor='e').grid(
        column=2, row=0, padx=(0, gui.WIDE_PAD), pady=gui.WIDE_PAD, sticky='ne'
    )
    filename = Entry(
        topFrame,
        textvariable=settings['filename'],
        exportselection=0,
        width=22,
        validate='key',
        validatecommand=(root.register(gui.validate_filename), '%P')
    )
    filename.grid(column=3, row=0, pady=gui.THIN_PAD, sticky='ne')
    filename.bind('<FocusOut>', lambda _: update_setting(['filename'], [settings['filename'].get()]))

    """ `Run` and `Settings` tabs """
    tabsFrame = Frame(root, padding=(gui.THIN_PAD, 0, gui.THIN_PAD, gui.THIN_PAD))
    tabsFrame.grid(column=0, row=1, **gui.uniform_padding, sticky='nesw')
    tabControl = Notebook(tabsFrame)
    runTab = Frame(tabControl, padding=(0, 0))
    settingsTab = Frame(tabControl, padding=(0, 0))
    settingsTab.rowconfigure(0, weight=1)
    settingsTab.rowconfigure(1, weight=1)
    tabControl.add(runTab, text='Run')
    tabControl.add(settingsTab, text='Settings')
    tabControl.pack(expand=1, fill='both')

    """ `Run` tab """
    summary = Labelframe(runTab, text='Summary')
    summary.grid(column=0, row=0, columnspan=3, **gui.lbf_asym_padding, sticky='nesw')

    uiChLabels = dict.fromkeys(channelIDs)  # Can be updated to reflect channels on/off
    for i, id in enumerate(channelIDs, start=1):
        uiChLabels[id] = Label(
            summary,
            text=id,
            font='bold',
            background=ui_textvar[f'ch{id}enabled']['bg'].get(),
            foreground=ui_textvar[f'ch{id}enabled']['fg'].get(),
            anchor='e'
        )
        uiChLabels[id].grid(
            column=i, row=0,
            padx=0 if i == 1 else (gui.THIN_PAD, 0), pady=(gui.WIDE_PAD, 0),
            sticky='we'
        )

    for i, entry in enumerate(
        ['Range (mV)', 'Offset (mV)', 'Coupling', 'Bandwidth', 'Trigger target'],
        start=1
    ):
        Label(summary, text=entry).grid(
            column=0, row=i, padx=(gui.THIN_PAD, 0),
            pady=(gui.WIDE_PAD if i == 1 else gui.LINE_PAD, 0), sticky='w'
        )

    for i, id in enumerate(channelIDs, start=1):
        padx = 0 if i == 1 else (gui.THIN_PAD, 0)
        Label(summary, textvariable=ui_textvar[f'ch{id}range'], anchor='e').grid(
            column=i, row=1, padx=padx, pady=(gui.WIDE_PAD, 0), sticky='e'
        )
        Label(summary, textvariable=ui_textvar[f'ch{id}analogOffset'], anchor='e').grid(
            column=i, row=2, padx=padx, pady=(gui.LINE_PAD, 0), sticky='e'
        )
        Label(summary, textvariable=ui_textvar[f'ch{id}coupling'], anchor='e').grid(
            column=i, row=3, padx=padx, pady=(gui.LINE_PAD, 0), sticky='e'
        )
        Label(summary, textvariable=ui_textvar[f'ch{id}bandwidth'], anchor='e').grid(
            column=i, row=4, padx=padx, pady=(gui.LINE_PAD, 0), sticky='e'
        )
        Label(summary, textvariable=ui_textvar[f'ch{id}target'], anchor='e').grid(
            column=i, row=5, padx=padx, pady=(gui.LINE_PAD, 0), sticky='e'
        )
    del padx

    gui.HSeparator(summary, row=6, columnspan=5)

    # Label(summary, text='Timebase').grid(
    #     column=0, row=6, padx=(gui.THIN_PAD, 0), pady=(gui.WIDE_PAD, 0), sticky='w'
    # )
    # Label(summary, textvariable=ui_textvar['timebase'], anchor='e').grid(
    #     column=1, row=6, columnspan=4, padx=0, pady=(gui.WIDE_PAD, 0), sticky='ew'
    # )
    Label(summary, text='Threshold').grid(
        column=0, row=7, padx=(gui.THIN_PAD, 0), pady=(gui.WIDE_PAD, 0), sticky='w'
    )
    Label(summary, textvariable=ui_textvar['thresholdmV'], anchor='e').grid(
        column=1, row=7, columnspan=4, padx=0, pady=(gui.WIDE_PAD, 0), sticky='ew'
    )
    Label(summary, text='Trigger delay').grid(
        column=0, row=8, padx=(gui.THIN_PAD, 0), pady=(gui.LINE_PAD, 0), sticky='w'
    )
    Label(summary, textvariable=ui_textvar['delaySeconds'], anchor='e').grid(
        column=1, row=8, columnspan=4, padx=0, pady=(gui.LINE_PAD, 0), sticky='ew'
    )
    Label(summary, text='Auto-trigger after').grid(
        column=0, row=9, padx=(gui.THIN_PAD, 0), pady=(gui.LINE_PAD, 0), sticky='w'
    )
    Label(summary, textvariable=ui_textvar['autoTrigms'], anchor='e').grid(
        column=1, row=9, columnspan=4, padx=0, pady=(gui.LINE_PAD, 0), sticky='ew'
    )
    Label(summary, text='Max. timeouts').grid(
        column=0, row=10, padx=(gui.THIN_PAD, 0), pady=(gui.LINE_PAD, 0), sticky='w'
    )
    Label(summary, textvariable=ui_textvar['maxTimeouts'], anchor='e').grid(
        column=1, row=10, columnspan=4, padx=0, pady=(gui.LINE_PAD, 0), sticky='ew'
    )
    Label(summary, text='Pre-trigger samples').grid(
        column=0, row=11, padx=(gui.THIN_PAD, 0), pady=(gui.LINE_PAD, 0), sticky='w'
    )
    Label(summary, textvariable=ui_textvar['preTrigSamples'], anchor='e').grid(
        column=1, row=11, columnspan=4, padx=0, pady=(gui.LINE_PAD, 0), sticky='ew'
    )
    Label(summary, text='Post-trigger samples').grid(
        column=0, row=12, padx=(gui.THIN_PAD, 0), pady=(gui.LINE_PAD, 0), sticky='w'
    )
    Label(summary, textvariable=ui_textvar['postTrigSamples'], anchor='e').grid(
        column=1, row=12, columnspan=4, padx=0, pady=(gui.LINE_PAD, 0), sticky='ew'
    )

    gui.HSeparator(summary, row=13, columnspan=5)

    logFlag = tk.IntVar(value=params['log'])
    logCheckBox = Checkbutton(
        summary,
        variable=logFlag,
        text='Log acquisition',
        takefocus=0,
        onvalue=1, offvalue=0,
        command=lambda: update_setting(['log'], [logFlag.get()])
    )
    logCheckBox.grid(
        column=0, row=14, columnspan=4,
        padx=(gui.THIN_PAD, 0), pady=(gui.WIDE_PAD, 0),
        sticky='sw'
    )

    """ Histogram """
    # TODO: adapt matplotlib canvas size to available space
    histogramLbf = Labelframe(runTab, text='Histogram')
    histogramLbf.grid(
        column=3, row=0, columnspan=6, rowspan=2, **gui.hist_padding, sticky='nesw'
    )

    Label(runTab, text='Bounds:', anchor='w').grid(
        column=3, row=2, padx=(gui.THIN_PAD, 0), pady=(gui.WIDE_PAD, 0), sticky='n'
    )
    histBounds = Slider(
        runTab,
        width=220,
        height=40,
        min_val=-100,
        max_val=200,
        init_lis=params['histBounds'],
        step_size=5,
        show_value=True,
        removable=False,
        addable=False
    )
    histBounds.grid(column=4, row=2, pady=(gui.THIN_PAD, 0), sticky='n')
    Label(runTab, text='Bins:', anchor='center').grid(
        column=5, row=2, padx=0, pady=(gui.WIDE_PAD + gui.THIN_PAD, 0), sticky='n'
    )
    histBinsVar = tk.IntVar(value=params['histBins'])

    binsSpbx = Spinbox(
        runTab,
        from_=50,
        to=200,
        textvariable=histBinsVar,
        width=6,
        increment=10,
        validate='key',
        validatecommand=(root.register(gui.validate_bins), '%P')
    )
    binsSpbx.grid(column=6, row=2, padx=(gui.MED_PAD, 0), pady=(gui.WIDE_PAD, 0), sticky='nw')
    binsSpbx.bind('<FocusOut>', lambda _: gui.assert_entry_ok(binsSpbx, (50, 200)))

    histogram = Histogram(parent=histogramLbf, xlim=histBounds.get(), bins=histBinsVar.get())

    Label(topFrame, text='Mode:').grid(column=0, row=0, sticky='w')
    modeVar = tk.StringVar(value=key_from_value(modes, params['mode']))
    modeSelector = OptionMenu(
        topFrame,
        modeVar,
        key_from_value(modes, params['mode']),
        *tuple(modes.keys()),
        command=lambda _: on_mode_change(modes[modeVar.get()], hist=histogram)
        )
    modeSelector.grid(column=1, row=0, padx=gui.WIDE_PAD, sticky='w')
    histogram.mode = modes[modeVar.get()]

    histogram.create()

    histApplyBtn = Button(
        runTab,
        text='Apply',
        width=8,
        command=lambda: histogram.create(
            histBounds.get(), histBinsVar.get(), widget_hook=histApplyBtn
        )
    )
    histApplyBtn.state(['disabled'])
    histApplyBtn.grid(
        column=7, row=2,
        padx=(gui.THIN_PAD, 0), pady=(gui.WIDE_PAD, 0), ipady=gui.THIN_PAD / 2,
        sticky='ne'
    )
    histSaveBtn = Button(runTab, text='Save as...', width=8, command=histogram.save)
    histSaveBtn.grid(
        column=8, row=2, padx=0, pady=(gui.WIDE_PAD, 0), ipady=gui.THIN_PAD / 2,
        sticky='ne'
    )
    # Enable Apply button if settings are changed
    for variable in [histBinsVar, histBounds.bars[0]['tkVar'], histBounds.bars[1]['tkVar']]:
        variable.trace_add(
            'write', lambda var, index, mode: toggle_widget_state(histApplyBtn)
        )

    """ Start/Stop job buttons """
    startButton = Button(
        runTab, text='START',
        command=lambda: histogram.start(root=root, max_timeouts=params['maxTimeouts'])
    )
    startButton.grid(
        column=0, row=1,
        padx=(gui.WIDE_PAD, 0), pady=0, ipadx=gui.THIN_PAD, ipady=gui.THIN_PAD,
        sticky='esw'
    )
    stopButton = Button(runTab, text='STOP', command=histogram.stop)
    stopButton.grid(
        column=1, row=1,
        padx=(gui.WIDE_PAD, 0), pady=0, ipadx=gui.THIN_PAD, ipady=gui.THIN_PAD,
        sticky='esw'
    )
    probeButton = Button(
        runTab, text='PROBE',
        command=lambda: probe_pico(
            root=root, mode=modes[modeVar.get()], max_timeouts=params['maxTimeouts']
        )
    )
    probeButton.grid(
        column=2, row=1,
        padx=(gui.WIDE_PAD, 0), pady=0, ipadx=gui.THIN_PAD, ipady=gui.THIN_PAD,
        sticky='esw'
    )

    """ Status textbox """
    statusFrame = Frame(runTab)
    statusFrame.grid(column=0, row=2, columnspan=3, padx=(gui.WIDE_PAD, 0), pady=(gui.WIDE_PAD, 0), sticky='nesw')
    Label(statusFrame, text='Status:').grid(column=0, row=0, sticky='sw')
    Label(statusFrame, textvariable=PV_STATUS).grid(column=1, row=0, sticky='sw')

    """ Settings tab. The 'settings' dictionary will temporarily store all the changes until
    the 'Apply' button is clicked, when such changes will be written to the config.ini file. """
    """ Trigger settings """
    def target_selection(flags: list[tk.StringVar], targets: tk.StringVar) -> None:
        targets.set(flags[0].get() + flags[1].get() + flags[2].get() + flags[3].get())

    centered_frame = Frame(settingsTab)
    centered_frame.place(in_=settingsTab, anchor='c', relx=.5, rely=.5)

    lbf_padding_v = {
        'padx': 0, 'pady': gui.WIDE_PAD, 'ipadx': gui.THIN_PAD, 'ipady': gui.THIN_PAD
    }
    triggerSettings = gui.PVLabelframe(
        centered_frame, title='Trigger', col=0, row=0, size=(1, 16), rspan=2,
        padding=lbf_padding_v, sticky='nsw'
    )

    targetFlags = [tk.StringVar(value='') for _ in range(4)]
    for i, name in enumerate(channelIDs):
        triggerSettings.add_checkbutton(
            id=f'ch{name}enabled',
            prompt=f'{name}',
            on_off=(f'{name}', ''),
            default=f'{name}' if f'{name}' in settings['target'].get() else '',
            command=lambda: target_selection(targetFlags, settings['target'])
        )
        triggerSettings.children[f'ch{name}enabled'][0].configure(
            state=['disabled'] if not params[f'ch{name}enabled'] else ['normal']
        )
        targetFlags[i] = triggerSettings.variables[f'ch{name}enabled']

    triggerSettings.add_spinbox(
        id='preTrigSamples',
        from_to=(0, 500),
        step=1,
        default=params['preTrigSamples'],
        prompt='Pre-trigger samples'
    )
    settings['preTrigSamples'] = triggerSettings.variables['preTrigSamples']

    triggerSettings.add_spinbox(
        id='postTrigSamples',
        from_to=(1, 500),
        step=1,
        default=params['postTrigSamples'],
        prompt='Post-trigger samples'
    )
    settings['postTrigSamples'] = triggerSettings.variables['postTrigSamples']

    # triggerSettings.add_spinbox(
    #     id='timebase',
    #     from_to=(0, 2 ** 32 - 1),
    #     step=1,
    #     prompt='Timebase',
    #     default=params['timebase']
    # )
    # settings['timebase'] = triggerSettings.variables['timebase']

    triggerSettings.add_spinbox(
        id='thresholdmV',
        from_to=(-chInputRanges[params[f"ch{params['target'][0]}range"]], 0),  # will need a better fix for this
        step=1,
        prompt='Threshold (mV)',
        default=int(params['thresholdmV'])
    )
    settings['thresholdmV'] = triggerSettings.variables['thresholdmV']

    triggerSettings.add_spinbox(
        id='autoTrigms',
        from_to=(500, 10000),
        step=100,
        prompt='Auto trigger (ms)',
        default=params['autoTrigms']
    )
    settings['autoTrigms'] = triggerSettings.variables['autoTrigms']

    triggerSettings.add_spinbox(
        id='delaySeconds',
        from_to=(0, 10),
        step=1,
        prompt='Trigger delay (s)',
        default=params['delaySeconds']
    )
    settings['delaySeconds'] = triggerSettings.variables['delaySeconds']

    triggerSettings.add_spinbox(
        id='maxTimeouts',
        from_to=(3, 10),
        step=1,
        prompt='Max. timeouts',
        default=params['maxTimeouts']
    )
    settings['maxTimeouts'] = triggerSettings.variables['maxTimeouts']

    triggerSettings.group(
        id='TARGETS',
        members=['chAenabled', 'chBenabled', 'chCenabled', 'chDenabled'],
        name='Target(s)',
        cspan=2
    )
    triggerSettings.arrange()

    """ Channels settings """
    chSettings = dict.fromkeys(channelIDs)
    for i, id in enumerate(channelIDs, start=1):
        chSettings[id] = ChannelSettings(
            centered_frame,
            name=id,
            col=i,
            row=0,
            target=triggerSettings.children[f'ch{id}enabled']
        )
        settings[f'ch{id}enabled'] = chSettings[id].frame.variables[f'ch{id}enabled']
        settings[f'ch{id}range'] = chSettings[id].frame.variables[f'ch{id}range']
        settings[f'ch{id}coupling'] = chSettings[id].frame.variables[f'ch{id}coupling']
        settings[f'ch{id}analogOffset'] = chSettings[id].frame.variables[f'ch{id}analogOffset']
        settings[f'ch{id}bandwidth'] = chSettings[id].frame.variables[f'ch{id}bandwidth']

        # Enable/disable channel settings and target channel(s) checkboxes in triggerSettings
        # chSettings.enabled_w.configure(
        #     command=lambda: [
        #         chSettings.toggle_channel_state(settings[f'ch{id}enabled'].get()),
        #         toggle_widget_state(
        #             triggerSettings.children[f'ch{id}enabled'][0],
        #             state='normal' if settings[f'ch{id}enabled'].get() else 'disabled'
        #         )
        #     ]
        # )
    
    """ File settings """
    fileSettings = gui.PVLabelframe(
        centered_frame, title='Data file', col=1, row=1, size=(2, 3), cspan=2,
        padding=gui.lbf_asym_padding_no_top, sticky='nesw'
    )
    fileSettings.add_checkbutton(
        id='count', prompt='Counter', default=params['includeCounter'], on_off=(1, 0)
    )
    settings['includeCounter'] = fileSettings.get_raw('count')
    includeAmplitude = fileSettings.add_checkbutton(
        id='amplitude', prompt='Amplitude', default=params['includeAmplitude'], on_off=(1, 0)
    )
    settings['includeAmplitude'] = fileSettings.get_raw('amplitude')
    toggle_widget_state(
        includeAmplitude, state='disabled' if modes[modeVar.get()] != 'adc' else 'normal'
    )
    includePeakToPeak = fileSettings.add_checkbutton(
        id='peakToPeak', prompt='Peak-to-peak', default=params['includePeakToPeak'], on_off=(1, 0)
    )
    settings['includePeakToPeak'] = fileSettings.get_raw('peakToPeak')
    toggle_widget_state(
        includePeakToPeak, state='disabled' if modes[modeVar.get()] != 'adc' else 'normal'
    )
    fileSettings.add_optionmenu(
        id='dataFileType', prompt='Save data as', default=params['dformat'], options=dataFileTypes
    )
    settings['dformat'] = fileSettings.get_raw('dataFileType')

    fileSettings.group(
        id='includedData',
        members=['count', 'amplitude', 'peakToPeak'],
        name='Data included in file',
        cspan=1
    )
    fileSettings.arrange()

    modeVar.trace_add(  # Disable `includeAmplitude` and `includePeakToPeak` if not in ADC
        'write',
        lambda var, index, mode: on_mode_change(
            modes[modeVar.get()], hook_widgets=[includeAmplitude, includePeakToPeak]
        )
    )

    """ Apply settings button """
    applySettingsBtn = Button(
        centered_frame,
        text='Apply',
        takefocus=False,
        command=lambda: apply_changes(settings, applySettingsBtn, uiChLabels)
    )
    applySettingsBtn.configure(state='disabled')  # Will only be enabled if a setting is changed
    applySettingsBtn.grid(
        column=4, row=1,
        padx=0, pady=(0, gui.WIDE_PAD), ipadx=gui.THIN_PAD, ipady=gui.THIN_PAD,
        sticky='se'
        )

    for variable in settings.values():  # Enable Apply button if any setting is changed
        variable.trace_add(
            'write', lambda var, index, mode: toggle_widget_state(applySettingsBtn)
        )

    root.center()
    try:
        pyi_splash_close()  # Close splash screen when app has loaded
    except NameError:
        pass
    root.mainloop()


if __name__ == '__main__':
    main()
