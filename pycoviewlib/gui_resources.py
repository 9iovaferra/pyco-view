""" Padding presets (frame padding: 'left top right bottom') """
THIN_PAD = 6
LINE_PAD = int(THIN_PAD / 3)
MED_PAD = int((THIN_PAD * 4) / 3)
WIDE_PAD = 2 * THIN_PAD
uniform_padding = {'padx': WIDE_PAD, 'pady': WIDE_PAD, 'ipadx': THIN_PAD, 'ipady': THIN_PAD}
asym_left_padding = {'padx': (WIDE_PAD, 0), 'pady': WIDE_PAD, 'ipadx': THIN_PAD, 'ipady': THIN_PAD}
hist_padding = {'padx': (WIDE_PAD, 0), 'pady': (WIDE_PAD, 0), 'ipadx': 0, 'ipady': 0}
lbf_padding = {'padx': WIDE_PAD, 'pady': WIDE_PAD, 'ipadx': THIN_PAD, 'ipady': THIN_PAD}
lbf_contents_padding = {'padx': (THIN_PAD, 0), 'pady': (MED_PAD, 2)} 

