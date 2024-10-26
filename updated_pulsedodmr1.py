from std_sequences.photoncounting import *
import numpy as np
from artiq.experiment import *

class UpdatedPulsedODMR1(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        self.setattr_device("ttl4")
        self.setattr_device("phaser0")
        self.setattr_argument("Experiment_Type", EnumerationValue(["pulsedodmr"], "pulsedodmr"))
        StdPhotonCounter.build(self)
        self.setattr_argument("green_init_duration",  NumberValue(1.0 * us, ndecimals=1, unit="us"))
        self.setattr_argument("rf_amplitude", NumberValue(0.2, ndecimals=2))
        self.setattr_argument("rf_duration", NumberValue(1.0 * us, ndecimals=3, unit="us"))
        self.setattr_argument("n_cycles", NumberValue(20000, ndecimals=0, step=1))
        self.setattr_argument("freq_high", NumberValue(3.075E3, ndecimals=1, step=1E2))
        self.setattr_argument("freq_center", NumberValue(2.875E3, ndecimals=1, step=1E2))  # Make this the center frequency on device.db file
        self.setattr_argument("freq_low", NumberValue(2.675E3, ndecimals=1, step=1E2))
        self.setattr_argument("freq_step", NumberValue(2, ndecimals=1, step=1E-1))
        self.setattr_argument('is_data_broadcast', BooleanValue(False))

    def prepare(self):
        self.frequency_list = np.arange(self.freq_low, self.freq_high + self.freq_step, self.freq_step)
        # self.frequency_list = np.array([2294, 2296, 2298, 2498, 2500, 2502])
    @kernel
    def run(self):
        # data_size = round(((self.freq_high + self.freq_step) - self.freq_low) / self.freq_step)
        data_size = len(self.frequency_list)
        print("list of all frequencies:", self.frequency_list, "data size:", data_size)
        self.turn_off_laser()                                    # keep green on entire time
        self.phaser_init()
        self.set_dataset("frequencies", self.frequency_list, broadcast=self.is_data_broadcast)
        self.set_dataset("on", np.full(data_size, np.nan), broadcast=self.is_data_broadcast)
        self.core.reset()
        for i in range(data_size):
            self.pulsedodmr(i)
            print("scanning frequency:", i)
            self.core.break_realtime()
        self.ttl4.off()
        print(data_size)
        print("experiment done")

    @kernel
    def pulsedodmr(self, index):
        self.phaser0.channel[0].set_duc_frequency((self.frequency_list[index] - self.freq_center) * MHz)  # set frequency (offset from 2.875 GHz)
        self.phaser0.duc_stb()
        cts = 0
        for j in range(self.n_cycles):
            self.ttl4.pulse(self.green_init_duration)
            self.phaser0.set_cfg(dac_txena=1)           # there's a 0.25us delay coming from  the phaser
            delay(self.rf_duration)
            self.phaser0.set_cfg(dac_txena=0)           # 0.25 sec delay again
            self.ttl4.on()  # self.counting_duration
            StdPhotonCounter.detect_edges_edge_counter(self)
            self.ttl4.off()
            #
            # self.ttl4.on()
            # self.ttl0_counter.set_config(count_rising=True, count_falling=False, send_count_event=False,
            #                                  reset_to_zero=True)
            # delay(self.counting_duration)
            # self.ttl0_counter.set_config(count_rising=False, count_falling=False, send_count_event=True,
            #                                  reset_to_zero=False)
            # self.ttl4.off()


            # self.mutate_dataset("on", ((index, index + 1), (j, j + 1)), StdPhotonCounter.count_edges_number_edge_counter(self))
            cts += self.ttl0_counter.fetch_count()
            delay(7.5 * us)
        self.core.break_realtime()
        self.mutate_dataset("on", index, cts)

    @kernel
    def turn_off_laser(self):
        self.core.reset()
        self.ttl4.off()

    @kernel
    def phaser_init(self):
        self.core.break_realtime()
        self.phaser0.init()
        self.phaser0.channel[0].set_att(0 * dB)
        self.phaser0.channel[0].set_duc_cfg()                   # set the digital upconverter
        self.phaser0.channel[0].oscillator[0].set_amplitude_phase(self.rf_amplitude, phase=0.)
        self.phaser0.channel[0].en_trf_out(rf=1, lo=0)
        self.phaser0.set_cfg(dac_txena=0)
