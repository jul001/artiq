import sys
from artiq.experiment import *

class PhaserRF1(EnvExperiment):

    def build(self):
        self.setattr_device("core")
        self.setattr_device("phaser0")
        self.setattr_argument("rf_output", NumberValue(2000, ndecimals=0, step=1))      # for the center frequency
        self.setattr_argument("f_ref", NumberValue(125, ndecimals=0, step=1))
        self.setattr_argument("rf_start", NumberValue(1475, ndecimals=0, step=1))       # What RF range we want to sweep
        self.setattr_argument("rf_end", NumberValue(4275, ndecimals=0, step=1))
        self.setattr_argument("rf_step", NumberValue(2, ndecimals=0, step=1))           # how much to step the RF

    @kernel
    def run(self):
        self.core.reset()
        # TRF372017.nint = 331
        # print(self.phaser0.channel[1].trf_mmap)
        # trf_mmap = TRF372017.get_mmap()
        # print(self.phaser0.channel[1].trf_mmap)
        # print(TRF372017.nint)
        self.phaser0.init()
        self.phaser0.channel[1].trf_write((
            0x9 |
            (2 << 5) | (0 << 19) | (1 << 20) |
            (0 << 21) | (0 << 26) |
            (0b1110 << 27)))
        self.phaser0.channel[1].trf_write((
            0xa |
            (23 << 5) | (0b01 << 21) |
            (0 << 23) | (2 << 26) |
            (0 << 28) | (0b00 << 29) |
            (0 << 31)))
        self.phaser0.channel[1].trf_write((
            0xe |
            (0x80 << 5) | (0x80 << 13) | (4 << 21) |
            (0 << 24) | (0 << 26) |
            (1 << 28) | (2 << 30)))
        self.phaser0.channel[1].cal_trf_vco()
        self.phaser0.set_cfg(clk_sel=0)
        self.phaser0.channel[1].set_duc_cfg()
        self.phaser0.channel[1].set_att(0 * dB)
        self.phaser0.channel[1].oscillator[0].set_amplitude_phase(1.0, phase=0.)
        self.phaser0.channel[1].set_duc_frequency(100 * MHz)
        self.phaser0.duc_stb()
        self.phaser0.channel[1].en_trf_out(rf=1)

        # lo: 1 pll: 1 rdv: 25 nt: 331 pr: 1 tx: 1   1655 MHz
        # lo: 1 pll: 1 rdv: 25 nt: 363 pr: 1 tx: 1   1815 MHz
        # lo: 1 pll: 1 rdv: 25 nt: 396 pr: 1 tx: 1   1980 MHz
        # lo: 1 pll: 1 rdv: 25 nt: 428 pr: 1 tx: 1   2140 Mhz
        # lo: 1 pll: 1 rdv: 25 nt: 461 pr: 1 tx: 1   2305 Mhz
        # lo: 0 pll: 0 rdv: 25 nt: 493 pr: 1 tx: 0   2465 Mhz
        # lo: 0 pll: 1 rdv: 10 nt: 131 pr: 1 tx: 0   3275 Mhz
        # lo: 0 pll: 1 rdv: 50 nt: 849 pr: 1 tx: 0   4245 MHz
