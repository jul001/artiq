from std_sequences.photoncounting import *
import numpy as np
from artiq.experiment import *

class UpdatedCWODMR2(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        self.setattr_device("ttl4")
        self.setattr_device("phaser0")
        self.setattr_argument("Experiment_Type", EnumerationValue(["cwodmr", "cwodmr with contrast"], "cwodmr"))
        StdPhotonCounter.build(self)
        self.setattr_argument("rf_amplitude", NumberValue(0.2, ndecimals=2))
        self.setattr_argument("n_cycles", NumberValue(100, ndecimals=0, step=1))
        self.setattr_argument("freq_high", NumberValue(3.075E3, ndecimals=1, step=1E2))
        self.setattr_argument("freq_center", NumberValue(2.875E3, ndecimals=1, step=1E2))  # Make this the center frequency on device.db file
        self.setattr_argument("freq_low", NumberValue(2.675E3, ndecimals=1, step=1E2))
        self.setattr_argument("freq_step", NumberValue(1, ndecimals=1, step=1E-1))
        self.setattr_argument('is_data_broadcast', BooleanValue(False))

    def prepare(self):
        self.frequency_list = np.arange(self.freq_low, self.freq_high + self.freq_step, self.freq_step)
        # self.frequency_list = np.array([2296, 2300, 2304, 2496, 2500, 2504])

    @kernel
    def run(self):
        data_size = round(((self.freq_high + self.freq_step) - self.freq_low) / self.freq_step)
        # data_size = len(self.frequency_list)
        print("list of all frequencies:", self.frequency_list, "data size:", data_size)
        self.turn_on_laser()                                    # keep green on entire time
        self.phaser_init()
        if self.Experiment_Type == "cwodmr":
            self.set_dataset("frequencies", self.frequency_list, broadcast=self.is_data_broadcast)
            self.set_dataset("on", np.full((self.n_cycles, data_size), np.nan), broadcast=self.is_data_broadcast)
            self.set_dataset("off", np.full((self.n_cycles, data_size), np.nan), broadcast=self.is_data_broadcast)

            self.core.reset()
            for i in range(self.n_cycles):
                self.cwodmr(i, data_size)
                # delay(0.3 * s) # added for temperature stability, comment out to have fastest runs
                print(i)
                self.core.break_realtime()
                #delay(125*us)
        # self.ttl4.off()
        self.phaser0.channel[1].en_trf_out(rf=0, lo=0)
        self.phaser0.set_cfg(dac_txena=0)
        print("experiment done")

    @kernel
    def cwodmr(self, index, data_size):
        for j in range(data_size):
            delay(125 * us)
            self.phaser0.channel[1].set_duc_frequency((self.frequency_list[j] - self.freq_center) * MHz)  # set frequency (offset from 2.875 GHz)
            self.phaser0.duc_stb()  # DUC register update
            self.phaser0.channel[1].oscillator[0].set_amplitude_phase(self.rf_amplitude, phase=0.)
            StdPhotonCounter.detect_edges_edge_counter(self)
            self.phaser0.channel[1].oscillator[0].set_amplitude_phase(0.0, phase=0.)
            self.mutate_dataset("on", ((index, index + 1), (j, j + 1)), StdPhotonCounter.count_edges_edge_counter(self))
            delay(125*us)
            StdPhotonCounter.detect_edges_edge_counter(self)
            self.mutate_dataset("off", ((index, index + 1), (j, j + 1)), StdPhotonCounter.count_edges_edge_counter(self))

    @kernel
    def turn_on_laser(self):
        self.core.reset()
        self.ttl4.on()

    @kernel
    def phaser_init(self):
        self.core.break_realtime()
        self.phaser0.init()
        self.phaser0.channel[1].set_att(0 * dB)
        self.phaser0.channel[1].set_duc_cfg()                   # set the digital upconverter
        self.phaser0.channel[1].oscillator[0].set_amplitude_phase(0.0, phase=0.)
        self.phaser0.channel[1].en_trf_out(rf=1, lo=0)
        self.phaser0.set_cfg(dac_txena=1)
