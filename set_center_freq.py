from artiq.experiment import *
import numpy as np
import math
from artiq.coredevice.trf372017 import TRF372017

class SetCenterFreq(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        self.setattr_device("core_dma")
        self.setattr_device("ttl4")
        self.setattr_device("phaser0")
        self.setattr_argument("center_frequency", NumberValue(2000, ndecimals=1, unit="MHz"))
        self.setattr_argument("TRF_Channel", NumberValue(1, ndecimals=0))

    def prepare(self):
        print("prepare")
        # print(self.calculate_params())
        self.calculate_params()
        self.trf0_mmap = TRF372017(self.calculate_params()).get_mmap()


    def calculate_params(self):
        MHz = 10 ** 6
        f_REF = 125 * 10 ** 6  # 125 MHz
        f_rf = int(self.center_frequency) # MHz

        div_comp = 0
        if f_rf < 600*MHz:
            div_comp=2
            f_rf = f_rf*4
        elif f_rf < 1200:
            div_comp=1
            f_rf=f_rf*2


        f_NMax = 400 * MHz  # to enter while loop

        # Target Step size
        f_step_rf = math.gcd(f_rf, f_REF)
        print(f_step_rf)
        # We are in INTEGER mode
        # LO_DIV_SEL
        if (f_rf <= 4800 * MHz and f_rf >= 2400 * MHz):
            LO_DIV_SEL = 1
        elif f_rf >= 1200 * MHz:
            LO_DIV_SEL = 2
        elif f_rf >= 600 * MHz:
            LO_DIV_SEL = 3
        else:
            LO_DIV_SEL = 4

        # f_VCO
        f_VCO = LO_DIV_SEL * f_rf

        # PLL_DIV_SEL
        PLL_DIV_SEL = int((LO_DIV_SEL * f_rf) / (3000 * MHz)) + 1

        while f_NMax > 375 * MHz:
            if PLL_DIV_SEL == 3:
                PLL_DIV_SEL = 4  # for now

            # print("LO_DIV_SEL: " + str(LO_DIV_SEL))
            # print("PLL_DIV_SEL: " + str(PLL_DIV_SEL))

            # solve for f_pfd
            f_PFD = (f_step_rf * LO_DIV_SEL) / (PLL_DIV_SEL)  # 2** lo_div
            # print("f_PFD: " + str(f_PFD / MHz) + "MHz")

            # RDIV requirement
            RDIV = f_REF / f_PFD
            # print("RDIV: " + str(RDIV))

            # NINT
            NINT = int((f_VCO * RDIV) / (f_REF * PLL_DIV_SEL))
            # print("NINT: " + str(NINT))

            # PRSC_SEL
            if NINT >= 72:
                PRSC_SEL = 1  # 8/9
                P = 8
            else:
                PRSC_SEL = 0  # 4/5
                P = 4

            print("PRSC_SEL: " + str(PRSC_SEL))

            f_NMax = f_VCO / (PLL_DIV_SEL * P)
            print("f_NMax: " + str(f_NMax / MHz) + "MHz")
            if f_NMax > 375 * MHz:
                PLL_DIV_SEL += 1
                # print(PLL_DIV_SEL)
                print("doesn't work, retrying... ")
                print()

        TX_DIV_SEL = LO_DIV_SEL
        print("For a target frequency: " + str(self.center_frequency / MHz) + " MHz")
        print()
        print("Conversion to Register Binary")
        print("LO_DIV_SEL: " + str(LO_DIV_SEL - 1))
        print("PLL_DIV_SEL: " + str(int(np.log2(PLL_DIV_SEL))))
        print("RDIV: " + str(RDIV))
        print("NINT: " + str(NINT))
        print("PRSC_SEL: " + str(PRSC_SEL))
        print("TX_DIV_SEL: " + str(LO_DIV_SEL - 1))

        LO_DIV_SEL = LO_DIV_SEL - 1 + div_comp
        PLL_DIV_SEL = int(np.log2(PLL_DIV_SEL))
        RDIV = RDIV
        NINT = NINT
        PRSC_SEL = PRSC_SEL


        trf_parameters = {
            "lo_div_sel": LO_DIV_SEL,
            "pll_div_sel": PLL_DIV_SEL,
            "rdiv": int(RDIV),
            "nint": NINT,
            "prsc_sel": PRSC_SEL,
            "tx_div_sel": LO_DIV_SEL
        }

        return trf_parameters

    @kernel
    def run(self):
        print("run")
        print("shutting off RF")
        channel = int(self.TRF_Channel)
        # I turned off all the RF here
        self.core.break_realtime()
        self.phaser0.init()
        self.phaser0.channel[channel].set_att(0 * dB)
        self.phaser0.channel[channel].set_duc_cfg()  # set the digital upconverter
        self.phaser0.channel[channel].oscillator[0].set_amplitude_phase(0.0, phase=0.)
        self.phaser0.channel[channel].en_trf_out(rf=0, lo=0)
        self.phaser0.set_cfg(dac_txena=0)


        # take previously generated mmap and write to the TRF0 (self.phaser0.channel[0])
        for data in self.trf0_mmap:
            # self.core.break_realtime()
            # print(data)
            self.phaser0.channel[channel].trf_write(data)
        self.core.break_realtime()

        # This is the VCO caliberation, taken from the PhaserChannel class so we can use our own mmap
        self.phaser0.channel[channel].trf_write(self.trf0_mmap[1] | (1 << 31))

        delay(2 * ms)
        print("Center frequency now set to: ", self.center_frequency)






