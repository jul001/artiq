from std_sequences.photoncounting import *
import numpy as np
from artiq.experiment import *
import random

class PODMR_testing(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        self.setattr_device("core_dma")
        self.setattr_device("ttl4")
        self.setattr_device("ttl6")
        self.setattr_device("phaser0")
        # self.setattr_device("ttl0_counter2")
        self.setattr_argument("Experiment_Type", EnumerationValue(["pulsedodmr"], "pulsedodmr"))
        StdPhotonCounter.build(self)
        self.setattr_argument("green_init_duration",  NumberValue(1.0 * us, ndecimals=1, unit="us"))
        self.setattr_argument("rf_amplitude", NumberValue(0.2, ndecimals=2))
        self.setattr_argument("rf_duration", NumberValue(1.0 * us, ndecimals=1, unit="us"))
        self.setattr_argument("n_cycles", NumberValue(20000, ndecimals=0, step=1))
        self.setattr_argument("freq_high", NumberValue(3.075E3, ndecimals=1, step=1E2))
        self.setattr_argument("freq_center", NumberValue(2.875E3, ndecimals=1, step=1E2))  # Make this the center frequency on device.db file
        self.setattr_argument("freq_low", NumberValue(2.675E3, ndecimals=1, step=1E2))
        self.setattr_argument("freq_step", NumberValue(2, ndecimals=1, step=1E-1))
        self.setattr_argument('is_data_broadcast', BooleanValue(False))

    def prepare(self):
        self.record_cycles = self.n_cycles
        self.playback_cycles = 1
        self.post_rf = 0.2*us
        self.ttl_delay = 0.2 * us
        if self.n_cycles >= 100000:
            rounded = int(round(self.n_cycles/100000) * 100000)
            print("rounding to: ", rounded)
            self.record_cycles = 100000
            self.playback_cycles = int(rounded / 100000)
        print("record cycles: ", self.record_cycles)
        print("plaback cycles: ", self.playback_cycles)
        print("n cycles: ", int(self.record_cycles * self.playback_cycles))
        self.experiment_length = self.green_init_duration + self.rf_duration + self.counting_duration + (self.ttl_delay) + self.post_rf
        self.rf_pseudo_start = self.experiment_length - ((1.9 * us) - self.green_init_duration)

        self.frequency_list = np.arange(self.freq_low, self.freq_high + self.freq_step, self.freq_step)
        print(self.frequency_list)
        # random.shuffle(self.frequency_list)
        # print(self.frequency_list)
        # self.frequency_list = np.array([3982, 3988, 3994])

    @kernel
    def record_rf(self):
        with self.core_dma.record("rf_collect"):
            self.ttl0_counter.set_config(count_rising=False, count_falling=False, send_count_event=False,
                                         reset_to_zero=True)
            for i in range(self.record_cycles):
                cursor = now_mu()
                delay(self.rf_pseudo_start)
                self.phaser0.channel[1].oscillator[0].set_amplitude_phase(self.rf_amplitude, phase=0.)
                delay(self.rf_duration)
                self.phaser0.channel[1].oscillator[0].set_amplitude_phase(0.0, phase=0.)

                at_mu(cursor)
                self.ttl4.pulse(self.green_init_duration)
                delay(self.rf_duration)
                cursor = now_mu() #updates to right where readout happens
                self.ttl4.on()
                delay(self.counting_duration)
                self.ttl4.off()

                at_mu(cursor)
                delay(self.ttl_delay)
                self.ttl0_counter.set_config(count_rising=True, count_falling=False, send_count_event=False,
                                             reset_to_zero=False)
                delay(self.counting_duration)
                self.ttl0_counter.set_config(count_rising=False, count_falling=False, send_count_event=False,
                                             reset_to_zero=False)
                delay(self.post_rf)
            self.ttl0_counter.set_config(count_rising=False, count_falling=False, send_count_event=True,
                                         reset_to_zero=False)

    @kernel
    def record_bg(self):
        with self.core_dma.record("bg_collect"):
            self.ttl0_counter.set_config(count_rising=False, count_falling=False, send_count_event=False,
                                         reset_to_zero=True)
            for j in range(self.record_cycles): #self.n_cycles
                self.ttl4.pulse(self.green_init_duration)
                delay(self.rf_duration)
                cursor = now_mu()
                self.ttl4.on()
                delay(self.counting_duration)
                self.ttl4.off()

                at_mu(cursor)
                delay(self.ttl_delay)
                self.ttl0_counter.set_config(count_rising=True, count_falling=False, send_count_event=False,
                                             reset_to_zero=False)
                delay(self.counting_duration)
                self.ttl0_counter.set_config(count_rising=False, count_falling=False, send_count_event=False,
                                             reset_to_zero=False)
                delay(self.post_rf)
            self.ttl0_counter.set_config(count_rising=False, count_falling=False, send_count_event=True,
                                         reset_to_zero=False)



    @kernel
    def run(self):
        print("hello, i am running :)")
        # data_size = round(((self.freq_high + self.freq_step) - self.freq_low) / self.freq_step)
        data_size = len(self.frequency_list)
        print("list of all frequencies:", self.frequency_list, "data size:", data_size)
        self.turn_off_laser()                                    # keep green on entire time
        self.phaser_init()
        self.record_rf()
        self.record_bg()
        self.set_dataset("frequencies", self.frequency_list, broadcast=self.is_data_broadcast)
        self.set_dataset("background", np.full(data_size, np.nan), broadcast=self.is_data_broadcast)
        self.set_dataset("on", np.full(data_size, np.nan), broadcast=self.is_data_broadcast)
        self.core.reset()
        rf_handle = self.core_dma.get_handle("rf_collect")
        self.core.break_realtime()
        bg_handle = self.core_dma.get_handle("bg_collect")
        self.core.break_realtime()
        oncounts = 0
        background = 0
        print("recordings prepped")
        self.core.break_realtime()
        for i in range(data_size):
            self.phaser0.channel[1].set_duc_frequency((self.frequency_list[i] - self.freq_center) * MHz)  # set frequency (offset from 2.875 GHz)
            self.phaser0.duc_stb()
            delay(125*us)
            oncounts = 0
            background = 0
            for j in range(self.playback_cycles):
                self.core_dma.playback_handle(rf_handle)
                oncounts += self.ttl0_counter.fetch_count()
                delay(10 * us)
                self.core_dma.playback_handle(bg_handle)
                background += self.ttl0_counter.fetch_count()
                delay(10 * us)
            self.mutate_dataset("on", i, oncounts)
            self.mutate_dataset("background", i, background)
            print("scanning frequency:", i, "/", data_size)
            self.core.break_realtime()
        self.ttl4.off()
        self.phaser0.channel[1].en_trf_out(rf=0, lo=0)
        self.phaser0.set_cfg(dac_txena=0)
        print(data_size)
        print("experiment done")

    @kernel
    def turn_off_laser(self):
        self.core.reset()
        self.ttl4.off()

    @kernel
    def phaser_init(self):
        self.core.break_realtime()
        self.phaser0.init()
        self.phaser0.channel[1].set_att(0 * dB)
        self.phaser0.channel[1].set_duc_cfg()                   # set the digital upconverter
        self.phaser0.channel[1].oscillator[0].set_amplitude_phase(0.0, phase=0.)
        # self.phaser0.channel[1].oscillator[0].set_amplitude_phase(self.rf_amplitude, phase=0.)

        self.phaser0.channel[1].en_trf_out(rf=1, lo=0)
        self.phaser0.set_cfg(dac_txena=1)
