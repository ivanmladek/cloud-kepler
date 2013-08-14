import sys
import base64
import numpy
from zlib import decompress, compress
import simplejson

#generates fake outputs for testing. Currently creates a zero noise square wave.
#the 20000 as seen below is the total data points
#the 200 as seen below is the number of data points per period
#the 100 as seen below is just the number of periods
#the 20 as seen below is the length of the transit in data points
#the 30 as seen below is the phase shift of the transit in data points
#-10 is an arbitrary depth for the transit
#when I have less pressing things to do this code will eventually have built in options and random noise and stuff. I just don't care right now.

def main(separator = '\t'):
    kic = 'your mom lol'
    q = '1234567'
    data = numpy.array([[x * .020433, 0] for x in xrange(20000)])
    for y in xrange(100):
        for x in xrange(20):
            data[(y*200 + x + 30)%20000][1] -= 10
    print "%s%s%s%s%s" % (kic, separator, q, separator, encode_list(data))
    
def encode_list(flux_list):
    return base64.b64encode(compress(simplejson.dumps(flux_list.tolist())))
	
if __name__ == "__main__":
    main()