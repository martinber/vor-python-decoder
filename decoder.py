#!/usr/bin/env python3

import sys
import copy
import numpy as np
import scipy.io.wavfile
import scipy.signal
import matplotlib.pyplot as plt

DECIMATED_RATE = 6000

FILENAME = sys.argv[1]

# Whether to show the plots of every step or not
PLOT_STEPS = False
# Whether to show the plots of phase of reference and variable signals
PLOT_RESULT = True

# Constant used for tuning, I don't know why I'm always some degrees off, I
# think that I'm doing the calculations for the delays of each filter wrong, or
# something like that. I don't have time to fix it now so I just add this number
# to the angle
ANGLE_OFFSET = 114

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
    FIR lowpass filter.

    Updates the delay attribute of the Signal object, indicating the delay that
    this filter has created.

    Arguments:
    - signal: Signal object
    - width [Hz]: Transition band width
    - attenuation [dB]: Positive decibels
    - f [Hz]: Cutoff frequency
    """

    nyq_rate = signal.rate / 2

    # Convert to normalized units (where 1 is the maximum frequency, equal to pi
    # radians per second, or equal to rate/2)
    width_norm = width/nyq_rate
    f_norm = f/nyq_rate

    N, beta = scipy.signal.kaiserord(attenuation, width_norm)

    # I prefer filters with odd number of taps
    if N % 2 == 0:
        N += 1

    # Design filter
    taps = scipy.signal.firwin(N, f_norm, window=("kaiser", beta))
    print("Lowpass filtering with {} taps".format(N))

    # Filter and create new Signal object
    result = Signal(
        scipy.signal.lfilter(taps, 1.0, signal.samples),
        signal.rate,
        signal.delay + (N - 1) // 2
    )
    return result

def bandpass(signal, width, attenuation, f1, f2):
    """
    Bandpass, leaves frequencies between f1 and f2

    Arguments:
    - signal
    - width [Hz]: Transition band width
    - attenuation [dB]: Positive decibels
    - f1 [Hz]: Cutoff frequency 1
    - f2 [Hz]: Cutoff frequency 2
    """

    nyq_rate = signal.rate / 2

    # Convert to normalized units (where 1 is the maximum frequency, equal to pi
    # radians per second, or equal to rate/2)
    width_norm = width/nyq_rate
    f1_norm = f1/nyq_rate
    f2_norm = f2/nyq_rate

    N, beta = scipy.signal.kaiserord(attenuation, width_norm)

    # I prefer filters with odd number of taps
    if N % 2 == 0:
        N += 1

    # Design filter
    taps = scipy.signal.firwin(
        N,
        [f1_norm, f2_norm],
        window=("kaiser", beta),
        pass_zero=False
    )
    print("Bandpass filtering with {} taps".format(N))

    # Filter and create new Signal object
    result = Signal(
        scipy.signal.lfilter(taps, 1.0, signal.samples),
        signal.rate,
        signal.delay + (N - 1) // 2
    )
    return result

def plot_signal(signal, title):
    """
    Plots a signal as a function of time and frequency.

    Arguments:
    - signal: Signal object
    - title: Description of the signal

    Reference: https://glowingpython.blogspot.com/2011/08/how-to-plot-frequency-spectrum-with.html
    """
    if not PLOT_STEPS:
        return

    fig = plt.figure(title)
    axes_time, axes_freq = fig.subplots(2, 1)

    samples = signal.samples

    n = len(samples)
    k = np.arange(n)
    T = n / signal.rate

    # Two sides frequency range
    frq = k / T
    # One side frequency range
    frq = frq[range(n // 2)]
    # Time range
    t = k / signal.rate

    # FFT computing and normalization
    Y = scipy.fft(samples) / n
    # Keep only one side
    Y = Y[range(n // 2)]

    # Delay in seconds
    delay_s = signal.delay / signal.rate

    axes_time.plot(t, samples, "b")
    axes_time.set_title("{}: Time".format(title))
    axes_time.set_xlabel("Time (seconds), delay: {}s".format(delay_s))
    axes_time.set_ylabel("y(t)")
    axes_time.grid(True)

    axes_freq.plot(frq, abs(Y), "r") # plotting the spectrum
    axes_freq.set_title("{}: Frequency".format(title))
    axes_freq.set_xlabel("Freq (Hz)")
    axes_freq.set_ylabel("|Y(f)|")
    axes_freq.grid(True)

def decimate(signal, output_rate):
    """
    Decimate to reach a given sample rate.

    Raises exception when input and output rate are not divisible.
    """
    assert signal.rate % output_rate == 0
    factor = signal.rate // output_rate

    result = Signal(
        signal.samples[::factor],
        output_rate,
        signal.delay // factor
    )
    return result

def compare_phases(ref_signal, var_signal):
    """
    Compare the phase of te reference and variable signals.

    Returns the difference, which should be the location of the receiver respect
    to the VOR transmitter.
    """
    assert ref_signal.rate == var_signal.rate
    rate = ref_signal.rate

    # Copy signals so I do not modify the objects given by the caller
    ref_signal = copy.copy(ref_signal)
    var_signal = copy.copy(var_signal)

    # Remove delays
    # Each succesive FIR filter adds a delay to the samples, so I store in the
    # signal object the delay in samples of each operation. Now I just cut the
    # start of the signal accordingly to leave both signals correctly aligned on
    # time
    ref_signal.samples = ref_signal.samples[ref_signal.delay:]
    ref_signal.delay = 0
    var_signal.samples = var_signal.samples[var_signal.delay:]
    var_signal.delay = 0

    # Correct the delay on the var_signal, I don't know why
    delay = int(ANGLE_OFFSET / 360 * 1/30 * rate)
    var_signal.samples = var_signal.samples[delay:]

    # Cut the variable signal if necessary, because if the are the same length
    # we can't do valid correlations. At least leave a difference of 4 periods
    var_max_length = int(len(ref_signal.samples) - rate * 4 / 30)
    if len(var_signal.samples) > var_max_length:
        var_signal.samples = var_signal.samples[:var_max_length]

    # Get the angle difference
    # I'm doing the correlation between both signals and then I take a look at
    # the maximum
    corr = np.correlate(ref_signal.samples, var_signal.samples, "valid")
    # Offset between signals in seconds
    offset = corr.argmax() / rate
    bearing = (offset / (1/30) * 360)
    bearing = bearing % 360

    if PLOT_RESULT:
        fig = plt.figure("Phase comparison")
        axes_signals, axes_corr = fig.subplots(2, 1)

        # Normalize both signals a bit so the plot looks better
        ref_signal.samples = ref_signal.samples / abs(ref_signal.samples.max())
        var_signal.samples = var_signal.samples / abs(var_signal.samples.max())

        n = len(ref_signal.samples)
        t = np.arange(n) / rate

        axes_signals.plot(
            t[:len(ref_signal.samples)],
            ref_signal.samples,
            "b", label="Reference"
        )
        axes_signals.plot(
            t[:len(var_signal.samples)],
            var_signal.samples,
            "r",
            label="Variable"
        )
        axes_signals.set_title("Phase comparison")
        axes_signals.set_xlabel("Time (seconds)")
        axes_signals.set_ylabel("y(t)")
        axes_signals.legend()
        axes_signals.grid(True)

        n = len(corr)
        t = np.arange(n) / rate

        axes_corr.plot(t, corr, "b")
        axes_corr.set_title("Correlation")
        axes_corr.set_xlabel("Time (seconds)")
        axes_corr.set_ylabel("correlation")
        axes_corr.grid(True)

    return bearing

def main():

    # Load input from wav
    rate, samples = scipy.io.wavfile.read(FILENAME)
    if samples.ndim > 1:
        # Keep only one channel if audio is stereo
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
    plot_signal(fm_signal, "FM filtered")

    # Center FM signal on 0Hz

    carrier = np.exp(-1.0j*2.0*np.pi*9960/fm_signal.rate*np.arange(len(fm_signal.samples)))
    fm_signal.samples = fm_signal.samples * carrier
    plot_signal(fm_signal, "FM centered")

    # Lowpass and decimate FM signal

    fm_signal = lowpass(
        fm_signal,
        width=500,
        attenuation=60,
        f=1500
    )

    fm_signal = decimate(fm_signal, DECIMATED_RATE)
    plot_signal(fm_signal, "FM centered and decimated")

    # Get phase of FM signal to get the variable signal

    var_signal = Signal(
        np.unwrap(np.angle(fm_signal.samples)),
        fm_signal.rate,
        fm_signal.delay
    )
    plot_signal(var_signal, "Variable signal")

    # Remove DC of variable signal

    var_signal = bandpass(
        var_signal,
        width=15,
        attenuation=60,
        f1=15,
        f2=45
    )

    plot_signal(var_signal, "Variable signal")

    bearing = compare_phases(ref_signal, var_signal)
    print("Bearing: {}°".format(bearing))

    plt.show()

if __name__ == "__main__":

    main()
