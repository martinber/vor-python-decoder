#!/usr/bin/env python3

import numpy as np
import scipy.io.wavfile
import scipy.signal
import matplotlib.pyplot as plt

FILENAME = "./sample_short.wav"

DEBUG_PLOTS = False


def lowpass(signal, rate, width, attenuation, f):
    """
    - signal
    - rate [Hz]: Signal ample rate
    - width [Hz]: Transition band width
    - attenuation [dB]: Positive decibels
    - f [Hz]: Cutoff frequency
    """

    nyq_rate = rate / 2.0

    width_norm = width/nyq_rate
    f_norm = f/nyq_rate

    N, beta = scipy.signal.kaiserord(attenuation, width_norm)
    taps = scipy.signal.firwin(N, f_norm, window=('kaiser', beta))

    if DEBUG_PLOTS:
        fig = plt.figure()
        axes_lst = fig.subplots(1, 1)
        axes_lst.plot(taps, 'o', linewidth=2)
        axes_lst.set_title("Lowpass filter taps")
        axes_lst.grid(True)

    print("Lowpass filtering with {} taps".format(N))

    return scipy.signal.lfilter(taps, 1.0, signal)

def bandpass(signal, rate, width, attenuation, f1, f2):
    """
    Bandpass, leaves frequencies between f1 and f2

    - signal
    - rate [Hz]: Signal ample rate
    - width [Hz]: Transition band width
    - attenuation [dB]: Positive decibels
    - f1 [Hz]: Cutoff frequency 1
    - f2 [Hz]: Cutoff frequency 2
    """

    nyq_rate = rate / 2.0

    width_norm = width/nyq_rate
    f1_norm = f1/nyq_rate
    f2_norm = f2/nyq_rate

    N, beta = scipy.signal.kaiserord(attenuation, width_norm)
    taps = scipy.signal.firwin(
        N,
        [f1_norm, f2_norm],
        window=('kaiser', beta),
        pass_zero=False
    )

    if DEBUG_PLOTS:
        fig = plt.figure()
        axes_lst = fig.subplots(1, 1)
        axes_lst.plot(taps, 'o', linewidth=2)
        axes_lst.set_title("Lowpass filter taps")
        axes_lst.grid(True)

    print("Bandpass filtering with {} taps".format(N))

    return scipy.signal.lfilter(taps, 1.0, signal)

def plot_signal(signal, rate, title):
    fig = plt.figure()
    axes_time, axes_freq = fig.subplots(2, 1)
    axes_time.plot(signal, '-', linewidth=2)
    axes_time.set_title("{}: Time".format(title))
    axes_time.grid(True)

    n = len(signal)
    k = np.arange(n)
    T = n/rate
    frq = k/T # two sides frequency range
    frq = frq[range(n//2)] # one side frequency range

    Y = scipy.fft(signal)/n # fft computing and normalization
    Y = Y[range(n//2)]

    axes_freq.plot(frq,abs(Y),'r') # plotting the spectrum
    axes_freq.set_xlabel('Freq (Hz)')
    axes_freq.set_ylabel('|Y(freq)|')
    axes_freq.set_title("{}: Frequency".format(title))


def decimate(signal, input_rate, output_rate):
    assert input_rate % output_rate == 0
    decimation = input_rate // output_rate
    return signal[::decimation]

if __name__ == "__main__":

    rate, signal = scipy.io.wavfile.read(FILENAME)
    print(rate)

    decimated_rate = 6000

    # Keep only one channel if audio is stereo
    if signal.ndim > 1:
        signal = signal[:, 0]


    #  plot_signal(signal, rate, "Input")

    # Filter 30Hz tone
    ref_signal = lowpass(
        signal,
        rate=rate,
        width=500,
        attenuation=60,
        f=500
    )

    ref_signal = decimate(ref_signal, rate, decimated_rate)
    #  plot_signal(ref_signal, decimated_rate, "Reference")

    # Filter FM
    fm_signal = bandpass(
        signal,
        rate=rate,
        width=500,
        attenuation=60,
        f1=8500,
        f2=11000
    )

    #  plot_signal(fm_signal, rate, "FM")

    # Move FM signal to center

    carrier = np.exp(-1.0j*2.0*np.pi* 10000/rate*np.arange(len(fm_signal)))
    fm_signal = fm_signal * carrier

    fm_signal = decimate(fm_signal, rate, decimated_rate)
    plot_signal(fm_signal.real, decimated_rate, "Decimated Centered FM real")
    plot_signal(fm_signal.imag, decimated_rate, "Decimated Centered FM imag")
    plot_signal(fm_signal, decimated_rate, "Decimated Centered FM")

    fm = fm_signal.real / fm_signal.real.max()
    scipy.io.wavfile.write("./fm.wav", decimated_rate, fm)

    plt.show()
