# -*- coding: utf-8 -*-

'''
BLS_PULSE algorithm, based on bls_pulse.pro originally written by Peter McCullough.
'''

import logging
import numpy as np
from utils import extreme

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def convert_duration_to_bins(duration_days, nbins, segment_size, duration_type):
    '''
    Convert the requested duration (in days) to a duration in (full) units of bins. I round
    down for min and round up for max, but I am not 100% that's what we want to necessarily
    be doing here.  Either way, I preferred being consistent than relying on pure rounding
    like it was done previously.

    Set type="min" if <duration_days> is a minimum duration, or set type="max" if it's a
    maximum duration.
    '''
    if duration_type == 'min':
        # This was the way it was calculated originally.
        # duration_bins = max(int(duration_days*nbins/segment_size),1)
        # Here is SWF's version as he understands it.
        duration_bins = max(int(np.floor(duration_days*nbins/segment_size)),1)
    elif duration_type == 'max':
        # This was the way it was calculated originally.
        # duration_bins = max(int(duration_days*nbins/segment_size),1)
        # Here is SWF's version as he understands it.
        duration_bins = max(1,min(int(np.ceil(duration_days*nbins/segment_size)), nbins))
    else:
        # Note (SWF): Need to add proper error handler here.
        duration_bins = 0

    return duration_bins


def calc_sr_max(n, nbins, mindur, maxdur, r_min, direction, trial_segment, binTime, binFlx, ppb,
this_seg, lc_samplerate):
    '''
    Convert the requested duration (in days) to a duration in units of bins.
    '''
    # Note (SWF):  I want to double check the math here matches what is done in
    # Kovacs et al. (2002).  On the TO-DO list...

    # Initialize output values to NaN.
    sr = np.nan
    thisDuration = np.nan
    thisDepth = np.nan
    thisMidTime = np.nan

    # Initialize the "best" Signal Residue to NaN.
    best_SR = np.nan

    for i1 in range(nbins):
        s = 0; r = 0

        for i2 in range(i1, min(i1 + maxdur + 1,nbins)):
            s += binFlx[i2]
            r += ppb[i2]

            if i2 - i1 >= mindur and r >= r_min and direction*s >= 0 and r < n:
                sr = s**2 / (r * (n - r))

                if sr > best_SR or np.isnan(best_SR):
                    # Update the best SR values.
                    best_SR = sr

                    # Report the duration in units of days, not bins.
                    thisDuration = binTime[i2] - binTime[i1]

                    # Update the depth.
                    thisDepth = extreme(binFlx[i1:i2+1], direction)

                    # Report the transit midtime in units of days.
                    thisMidTime = (binTime[i2] + binTime[i1]) / 2.

    # Return a tuple containing the Signal Residue and corresponding signal information.
    # If no Signal Residue was calculated in the loop above, then these will all be NaN's.
    return (best_SR, thisDuration, thisDepth, thisMidTime)


def bls_pulse(time, flux, fluxerr, n_bins, segment_size, min_duration, max_duration,
direction=0, print_format='none', verbose=False, detrend_order=0):
    # The number of bins can sometimes change, so make a working copy so that the original
    # value is still available.
    nbins = n_bins

    # Calculate the time baseline of this lightcurve (this will be in days).
    lightcurve_timebaseline = time[-1] - time[0]

    # Convert the min and max transit durations to units of bins from units of days.
    mindur = convert_duration_to_bins(min_duration, nbins, segment_size, duration_type="min")
    maxdur = convert_duration_to_bins(max_duration, nbins, segment_size, duration_type="max")

    # Extract lightcurve information and mold it into numpy arrays.
    # First identify which elements are not finite and remove them.
    ndx = np.isfinite(flux)
    time = time[ndx]
    flux = flux[ndx]

    # Define the minimum "r" value.  Note that "r" is the sum of the weights on flux at
    # full depth.
    # NOTE:  The sample rate of Kepler long-cadence data is (within a second) 0.02044 days.
    # Rather than hard-code this, we determine the sample rate from the input lightcurve as
    # just the median value of the difference between adjacent observations.  Assuming the
    # input lightcurve has enough points, then this will effectively avoid issues caused by
    # gaps in the lightcurve, since we assume that *most* of the data points in the lightcurve
    # array will be taken at the nominal sampling.  We also do this so that, if we are sending
    # simulated data at a different cadence than the Kepler long-cadence, then we don't have
    # to add conditionals to the code.
    lc_samplerate = np.median(np.diff(time))

    # The min. r value to consider is either the typical number of Kepler data points expected
    # in a signal that is min_duration long, or a single data point, whichever is larger.
    r_min = int(np.ceil(min_duration / lc_samplerate))

    # Divide the input time and flux arrays into segments.
    #seg_stepsize = int(round(segment_size / lc_samplerate))
    #segments = [(x,time[x:x+seg_stepsize]) for x in xrange(0,len(time),seg_stepsize)]
    #flux_segments = [(x,flux_minus_mean[x:x+seg_stepsize]) for x in
    #    xrange(0,len(flux_minus_mean),seg_stepsize)]
    nsegments = int(np.floor((np.amax(time) - np.amin(time)) / segment_size) + 1.)
    segments = [(q,time[(time >= q*segment_size) & (time < (q+1)*segment_size)]) for
        q in xrange(nsegments)]
    flux_segments = [(q,flux[(time >= q*segment_size) & (time < (q+1)*segment_size)]) for
        q in xrange(nsegments)]

    # Initialize storage arrays for output values.  We don't know how many signals we will find,
    # so for now these are instantiated without a length and we make use of the (more inefficient)
    # "append" method in numpy to grow the array.  This could be one area that could be made more
    # efficient if speed is a concern, e.g., by making these a sufficiently large size, filling
    # them in starting from the first index, and then remove those that are empty at the end.  A
    # sufficiently large size could be something like the time baseline of the lightcurve divided
    # by the min. transit duration being considered, for example.
    # I think we sort of do now how long they are going to be, we are finding the best signal for
    # each segment so it'll come out equal to the number of segments. It was just programmed
    # this way, probably inefficient though.
    srMax = np.array([], dtype='float64')
    transitDuration = np.array([], dtype='float64')
    transitMidTime = np.array([], dtype='float64')
    transitDepth = np.array([], dtype='float64')

    # For each segment of this lightcurve, bin the data points into appropriate segments,
    # normalize the binned fluxes, and calculate SR_Max.  If the new SR value is greater than
    # the previous SR_Max value, store it as a potential signal.
    # NOTE: "sr" is the Signal Residue as defined in the original BLS paper by
    # Kovacs et al. (2002), A&A, 391, 377.
    for jj,seg,flux_seg in zip(range(len(segments)),segments,flux_segments):
        # Print progress information to screen, if verbose is set.
        if verbose:
            txt = 'KIC' + kic_id + ' | Segment  ' +  str(jj+1) + ' out of ' + str(len(segments))
            logger.info(txt)

        # Default this segment's output values to NaN.  If a valid SR_Max is found, these will
        # be updated with finite values.
        srMax = np.append(srMax, np.nan)
        transitDuration = np.append(transitDuration, np.nan)
        transitMidTime = np.append(transitMidTime, np.nan)
        transitDepth = np.append(transitDepth, np.nan)

        # Bin the data points.  First extract the segment number and segment array, then count
        # how many points in this segment.
        l,this_seg = seg
        ll,this_flux_seg = flux_seg
        n = this_seg.size

        # Make sure the number of bins is not greater than the number of data points in this
        # segment.
        nbins = int(n_bins)
        if n < nbins:
            nbins = n
            mindur = convert_duration_to_bins(min_duration, nbins, segment_size,
                duration_type="min")
            maxdur = convert_duration_to_bins(max_duration, nbins, segment_size,
                duration_type="max")

        # NOTE: Modified by emprice.
        # See http://stackoverflow.com/questions/6163334/binning-data-in-python-with-scipy-numpy
        # Compute average times and fluxes in each bin, and count the number of points per
        # bin.
        bin_slices = np.linspace(float(jj) * segment_size, float(jj + 1) * segment_size, nbins+1)
        bin_memberships = np.digitize(this_seg, bin_slices)
        binned_times = [this_seg[bin_memberships == i].mean() for i in range(1, len(bin_slices))]
        binned_fluxes = [this_flux_seg[bin_memberships == i].mean() for i in
            range(1, len(bin_slices))]
        ppb = [len(this_seg[bin_memberships == i]) for i in range(1, len(bin_slices))]

        # TODO: Detrending!

        # Determine SR_Max.  The return tuple consists of:
        #      (Signal Residue, Signal Duration, Signal Depth, Signal MidTime)
        sr_tuple = calc_sr_max(n, nbins, mindur, maxdur, r_min, direction, segment_size,
            binned_times, binned_fluxes, ppb, this_seg, lc_samplerate)

        # If the Signal Residue is finite, then we need to add these parameters to our output
        # storage array.
        if np.isfinite(sr_tuple[0]):
            srMax[-1] = sr_tuple[0]
            transitDuration[-1] = sr_tuple[1]
            transitDepth[-1] = sr_tuple[2]
            transitMidTime[-1] = sr_tuple[3]

        # Print output.
        if print_format == 'encoded':
            print "\t".join([str(kic_id), encode_array(srMax), encode_array(transitDuration),
                encode_array(transitDepth), encode_array(transitMidTime)])
        elif print_format == 'normal':
            print "-" * 80
            print "Kepler " + kic_id
            print "Quarters: " + quarters
            print "-" * 80
            print '{0: <7s} {1: <13s} {2: <10s} {3: <9s} {4: <13s}'.format('Segment', 'srMax',
                'Duration', 'Depth', 'MidTime')
            for ii, seq in enumerate(segments):
                print '{0: <7d} {1: <13.6f} {2: <10.6f} {3: <9.6f} {4: <13.6f}'.format(ii,
                    srMax[ii], transitDuration[ii], transitDepth[ii], transitMidTime[ii])
            print "-" * 80
            print
            print

    # Return each segment's best transit event.  Create a pandas data frame based on the
    # array of srMax and transit parameters.  The index of the pandas array will be the
    # segment number.
    return_data = dict(srsq=srMax, duration=transitDuration, depth=transitDepth,
        midtime=transitMidTime)
    return return_data


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    logger.setLevel(logging.INFO)
    main()
