#!/usr/bin/env python3

import numpy as np
import scipy.io.wavfile
import scipy.signal
import matplotlib.pyplot as plt

FILENAME = "./sample_short.wav"

DEBUG_PLOTS = False
DECIMATED_RATE = 6000

class Signal:

    def __init__(self, samples, rate, delay=0):
        """
        Keeps the data of a signal and sample rate tied together.

        Also keeps track of the delay that this signal has, each FIR filter adds
        a delay of N/2 being N the number of taps. At the end I need the delays
        of each signal to compare the phase of them.
        """
        self.samples = samples
        self.rate = rate
        self.delay = delay


def lowpass(signal, width, attenuation, f):
    """
    - signal
    - width [Hz]: Transition band width
    - attenuation [dB]: Positive decibels
    - f [Hz]: Cutoff frequency
    """

    nyq_rate = signal.rate / 2.0

    width_norm = width/nyq_rate
    f_norm = f/nyq_rate

    N, beta = scipy.signal.kaiserord(attenuation, width_norm)

    if N % 2 == 0:
        N += 1

    taps = scipy.signal.firwin(N, f_norm, window=('kaiser', beta))

    if DEBUG_PLOTS:
        fig = plt.figure()
        axes_lst = fig.subplots(1, 1)
        axes_lst.plot(taps, 'o', linewidth=2)
        axes_lst.set_title("Lowpass filter taps")
        axes_lst.grid(True)

    print("Lowpass filtering with {} taps".format(N))

    result = Signal(
        scipy.signal.lfilter(taps, 1.0, signal.samples),
        signal.rate,
        signal.delay + (N - 1) // 2
    )
    return result

def bandpass(signal, width, attenuation, f1, f2):
    """
    Bandpass, leaves frequencies between f1 and f2

    - signal
    - width [Hz]: Transition band width
    - attenuation [dB]: Positive decibels
    - f1 [Hz]: Cutoff frequency 1
    - f2 [Hz]: Cutoff frequency 2
    """

    nyq_rate = signal.rate / 2.0

    width_norm = width/nyq_rate
    f1_norm = f1/nyq_rate
    f2_norm = f2/nyq_rate

    N, beta = scipy.signal.kaiserord(attenuation, width_norm)

    if N % 2 == 0:
        N += 1

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

    result = Signal(
        scipy.signal.lfilter(taps, 1.0, signal.samples),
        signal.rate,
        signal.delay + (N - 1) // 2
    )
    return result

def plot_signal(signal, title):
    fig = plt.figure()
    axes_time, axes_freq = fig.subplots(2, 1)

    samples = signal.samples

    n = len(samples)
    k = np.arange(n)
    t = k/signal.rate
    T = n/signal.rate
    frq = k/T # two sides frequency range
    frq = frq[range(n//2)] # one side frequency range

    Y = scipy.fft(samples)/n # fft computing and normalization
    Y = Y[range(n//2)]

    axes_time.plot(t, samples, '-', linewidth=2)
    axes_time.set_title("{}: Time".format(title))
    axes_time.set_xlabel("Time (seconds), delay: {}s".format(signal.delay / signal.rate))
    axes_time.set_ylabel('y')
    axes_time.grid(True)

    axes_freq.plot(frq, abs(Y), 'r') # plotting the spectrum
    axes_freq.set_xlabel('Freq (Hz)')
    axes_freq.set_ylabel('|Y(freq)|')
    axes_freq.set_title("{}: Frequency".format(title))
    axes_freq.grid(True)

def decimate(signal, output_rate):
    """
    Decimate to reach a given sample rate.

    Raises exception when input and output rate are not are not divisible
    """
    assert signal.rate % output_rate == 0
    decimation = signal.rate // output_rate

    result = Signal(
        signal.samples[::decimation],
        output_rate,
        signal.delay // decimation
    )
    return result

def compare_phases(ref_signal, var_signal):
    fig = plt.figure()
    axes = fig.subplots(1, 1)

    assert ref_signal.rate == var_signal.rate

    # Remove delays

    print(ref_signal.delay)
    print(var_signal.delay)
    ref_signal.samples = ref_signal.samples[ref_signal.delay:] / abs(ref_signal.samples.max())
    ref_signal.delay = 0
    var_signal.samples = var_signal.samples[var_signal.delay:] / abs(var_signal.samples.max())
    var_signal.delay = 0

    # Plot

    n = len(samples)
    k = np.arange(n)
    t = k/ref_signal.rate

    axes.plot(t[:len(ref_signal.samples)], ref_signal.samples, 'b', label="Reference")
    axes.plot(t[:len(var_signal.samples)], var_signal.samples, 'r', label="Variable")
    axes.set_title("Reference vs variable signal")
    axes.set_xlabel("Time (seconds)")
    axes.set_ylabel('y')
    axes.legend()
    axes.grid(True)


    result = 0
    for (n,), x in np.ndenumerate(ref_signal.samples):
        result += x * np.exp(-1.0j * 30/ref_signal.rate * n)
    ref_phase = np.angle(result) / (2*np.pi) * 360

    result = 0
    for (n,), x in np.ndenumerate(var_signal.samples):
        result += x * np.exp(-1.0j * 30/var_signal.rate * n)
    var_phase = np.angle(result) / (2*np.pi) * 360

    angle = (var_phase - ref_phase) % 360
    print(angle)

if __name__ == "__main__":

    # Load input from wav

    rate, samples = scipy.io.wavfile.read(FILENAME)
    # Keep only one channel if audio is stereo
    if samples.ndim > 1:
        samples = samples[:, 0]
    input_signal = Signal(samples, rate)
    print("Input sample rate:", rate)

    plot_signal(input_signal, "Input")


    # Filter and decimate reference signal, a 30Hz tone

    ref_signal = lowpass(
        input_signal,
        width=500,
        attenuation=60,
        f=500
    )
    ref_signal = decimate(ref_signal, DECIMATED_RATE)
    plot_signal(ref_signal, "Reference signal")

    # Filter FM signal

    fm_signal = bandpass(
        input_signal,
        width=1000,
        attenuation=60,
        f1=8500,
        f2=11500
    )

    #  plot_signal(fm_signal, "FM filtered")

    # Center FM signal on 0Hz

    carrier = np.exp(-1.0j*2.0*np.pi*10000/fm_signal.rate*np.arange(len(fm_signal.samples)))
    fm_signal.samples = fm_signal.samples * carrier

    #  plot_signal(fm_signal, "FM centered")

    # Lowpass and decimate FM signal

    fm_signal = lowpass(
        fm_signal,
        width=500,
        attenuation=60,
        f=1500
    )

    fm_signal = decimate(fm_signal, DECIMATED_RATE)

    #  plot_signal(fm_signal, "FM centered and filtered")

    # Get phase of FM signal to get the variable signal

    var_signal = Signal(
        np.unwrap(np.angle(fm_signal.samples)),
        fm_signal.rate,
        fm_signal.delay
    )
    #  plot_signal(var_signal, "Variable signal")

    # Remove DC of variable signal

    var_signal = bandpass(
        var_signal,
        width=15,
        attenuation=60,
        f1=15,
        f2=45
    )

    plot_signal(var_signal, "Variable signal")

    compare_phases(ref_signal, var_signal)

    plt.show()
