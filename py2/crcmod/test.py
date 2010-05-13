#-----------------------------------------------------------------------------
# Copyright (c) 2010  Raymond L. Buvel
# Copyright (c) 2010  Craig McQueen
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#-----------------------------------------------------------------------------
'''Unit tests for crcmod functionality'''


import unittest

import binascii

from crcmod import mkCrcFun, Crc
from crcmod import _usingExtension
from predefined import PredefinedCrc
from predefined import mkPredefinedCrcFun
from predefined import _crc_definitions as _predefined_crc_definitions


#-----------------------------------------------------------------------------
# This polynomial was chosen because it is the product of two irreducible
# polynomials.
# g8 = (x^7+x+1)*(x+1)
g8 = 0x185

#-----------------------------------------------------------------------------
# The following reproduces all of the entries in the Numerical Recipes table.
# This is the standard CCITT polynomial.
g16 = 0x11021

#-----------------------------------------------------------------------------
g24 = 0x15D6DCB

#-----------------------------------------------------------------------------
# This is the standard AUTODIN-II polynomial which appears to be used in a
# wide variety of standards and applications.
g32 = 0x104C11DB7


#-----------------------------------------------------------------------------
# I was able to locate a couple of 64-bit polynomials on the web.  To make it
# easier to input the representation, define a function that builds a
# polynomial from a list of the bits that need to be turned on.

def polyFromBits(bits):
    p = 0L
    for n in bits:
        p = p | (1L << n)
    return p

# The following is from the paper "An Improved 64-bit Cyclic Redundancy Check
# for Protein Sequences" by David T. Jones

g64a = polyFromBits([64, 63, 61, 59, 58, 56, 55, 52, 49, 48, 47, 46, 44, 41,
            37, 36, 34, 32, 31, 28, 26, 23, 22, 19, 16, 13, 12, 10, 9, 6, 4,
            3, 0])

# The following is from Standard ECMA-182 "Data Interchange on 12,7 mm 48-Track
# Magnetic Tape Cartridges -DLT1 Format-", December 1992.

g64b = polyFromBits([64, 62, 57, 55, 54, 53, 52, 47, 46, 45, 40, 39, 38, 37,
            35, 33, 32, 31, 29, 27, 24, 23, 22, 21, 19, 17, 13, 12, 10, 9, 7,
            4, 1, 0])

#-----------------------------------------------------------------------------
# This class is used to check the CRC calculations against a direct
# implementation using polynomial division.

class poly:
    '''Class implementing polynomials over the field of integers mod 2'''
    def __init__(self,p):
        p = long(p)
        if p < 0: raise ValueError('invalid polynomial')
        self.p = p

    def __long__(self):
        return self.p

    def __eq__(self,other):
        return self.p == other.p

    def __ne__(self,other):
        return self.p != other.p

    # To allow sorting of polynomials, use their long integer form for
    # comparison
    def __cmp__(self,other):
        return cmp(self.p, other.p)

    def __nonzero__(self):
        return self.p != 0L

    def __neg__(self):
        return self # These polynomials are their own inverse under addition

    def __invert__(self):
        n = max(self.deg() + 1, 1)
        x = (1L << n) - 1
        return poly(self.p ^ x)

    def __add__(self,other):
        return poly(self.p ^ other.p)

    def __sub__(self,other):
        return poly(self.p ^ other.p)

    def __mul__(self,other):
        a = self.p
        b = other.p
        if a == 0 or b == 0: return poly(0)
        x = 0L
        while b:
            if b&1:
                x = x ^ a
            a = a<<1
            b = b>>1
        return poly(x)

    def __divmod__(self,other):
        u = self.p
        m = self.deg()
        v = other.p
        n = other.deg()
        if v == 0: raise ZeroDivisionError('polynomial division by zero')
        if n == 0: return (self,poly(0))
        if m < n: return (poly(0),self)
        k = m-n
        a = 1L << m
        v = v << k
        q = 0L
        while k > 0:
            if a & u:
                u = u ^ v
                q = q | 1L
            q = q << 1
            a = a >> 1
            v = v >> 1
            k -= 1
        if a & u:
            u = u ^ v
            q = q | 1L
        return (poly(q),poly(u))

    def __div__(self,other):
        return self.__divmod__(other)[0]

    def __mod__(self,other):
        return self.__divmod__(other)[1]

    def __repr__(self):
        return 'poly(0x%XL)' % self.p

    def __str__(self):
        p = self.p
        if p == 0: return '0'
        lst = { 0:[], 1:['1'], 2:['x'], 3:['1','x'] }[p&3]
        p = p>>2
        n = 2
        while p:
            if p&1: lst.append('x^%d' % n)
            p = p>>1
            n += 1
        lst.reverse()
        return '+'.join(lst)

    def deg(self):
        '''return the degree of the polynomial'''
        a = self.p
        if a == 0: return -1
        n = 0
        while a >= 0x10000L:
            n += 16
            a = a >> 16
        a = int(a)
        while a > 1:
            n += 1
            a = a >> 1
        return n

#-----------------------------------------------------------------------------
# The following functions compute the CRC using direct polynomial division.
# These functions are checked against the result of the table driven
# algorithms.

g8p = poly(g8)
x8p = poly(1L<<8)
def crc8p(d):
    d = map(ord, d)
    p = 0L
    for i in d:
        p = p*256L + i
    p = poly(p)
    return long(p*x8p%g8p)

g16p = poly(g16)
x16p = poly(1L<<16)
def crc16p(d):
    d = map(ord, d)
    p = 0L
    for i in d:
        p = p*256L + i
    p = poly(p)
    return long(p*x16p%g16p)

g24p = poly(g24)
x24p = poly(1L<<24)
def crc24p(d):
    d = map(ord, d)
    p = 0L
    for i in d:
        p = p*256L + i
    p = poly(p)
    return long(p*x24p%g24p)

g32p = poly(g32)
x32p = poly(1L<<32)
def crc32p(d):
    d = map(ord, d)
    p = 0L
    for i in d:
        p = p*256L + i
    p = poly(p)
    return long(p*x32p%g32p)

g64ap = poly(g64a)
x64p = poly(1L<<64)
def crc64ap(d):
    d = map(ord, d)
    p = 0L
    for i in d:
        p = p*256L + i
    p = poly(p)
    return long(p*x64p%g64ap)

g64bp = poly(g64b)
def crc64bp(d):
    d = map(ord, d)
    p = 0L
    for i in d:
        p = p*256L + i
    p = poly(p)
    return long(p*x64p%g64bp)


#-----------------------------------------------------------------------------
# The binascii module has a 32-bit CRC function that is used in a wide range
# of applications including the checksum used in the ZIP file format.  This
# test is to use crcmod to reproduce the same function.
def reference_crc32(d, crc=0):
    # Work around the future warning on constants.
    if crc > 0x7FFFFFFFL:
        x = int(crc & 0x7FFFFFFFL)
        crc = x | -2147483648
    x = binascii.crc32(d,crc)
    return long(x) & 0xFFFFFFFFL


class KnownAnswerTests(unittest.TestCase):
    known_answers = [
        [ (g8,0,0),             0xFE,           0x9D        ],
        [ (g8,-1,1),            0x4F,           0x9B        ],
        [ (g8,0,1),             0xFE,           0x62        ],
        [ (g16,0,0),            0x1A71,         0xE556      ],
        [ (g16,-1,1),           0x1B26,         0xF56E      ],
        [ (g16,0,1),            0x14A1,         0xC28D      ],
        [ (g24,0,0),            0xBCC49D,       0xC4B507    ],
        [ (g24,-1,1),           0x59BD0E,       0x0AAA37    ],
        [ (g24,0,1),            0xD52B0F,       0x1523AB    ],
        [ (g32,0,0),            0x6B93DDDB,     0x12DCA0F4  ],
        [ (g32,0xFFFFFFFFL,1),  0x41FB859FL,    0xF7B400A7L ],
        [ (g32,0,1),            0x6C0695EDL,    0xC1A40EE5L ],
        [ (g32,0,1,0xFFFFFFFF), 0xBE047A60L,    0x084BFF58L ],
    ]

    def test_known_answers(self):
        msg = 'CatMouse987654321'
        for crcfun_params, v0, v1 in self.known_answers:
            crcfun = mkCrcFun(*crcfun_params)            self.assertEqual(crcfun('',0), 0, "Wrong answer for CRC parameters %s, input ''" % (crcfun_params,))
            self.assertEqual(crcfun('T'), v0, "Wrong answer for CRC parameters %s, input 'T'" % (crcfun_params,))            self.assertEqual(crcfun(msg), v1, "Wrong answer for CRC parameters %s, input '%s'" % (crcfun_params,msg))            self.assertEqual(crcfun(msg[4:], crcfun(msg[:4])), v1, "Wrong answer for CRC parameters %s, input '%s'" % (crcfun_params,msg))            self.assertEqual(crcfun(msg[-1], crcfun(msg[:-1])), v1, "Wrong answer for CRC parameters %s, input '%s'" % (crcfun_params,msg))


class CompareReferenceCrcTest(unittest.TestCase):
    test_messages = [
        '',
        '123456789',
        'CatMouse987654321',
    ]

    test_poly_crcs = [
        [ (g8,0,0),     crc8p    ],
        [ (g16,0,0),    crc16p   ],
        [ (g24,0,0),    crc24p   ],
        [ (g32,0,0),    crc32p   ],
        [ (g64a,0,0),   crc64ap  ],
        [ (g64b,0,0),   crc64bp  ],
    ]

    def test_compare_crc32(self):
        # The following function should produce the same result as reference_crc32.
        crc32 = mkCrcFun(g32,0,1,0xFFFFFFFF)

        for msg in self.test_messages:
            self.assertEqual(crc32(msg), reference_crc32(msg))

    def test_compare_poly(self):
        for crcfun_params, crc_poly_fun in self.test_poly_crcs:
            # The following function should produce the same result as
            # the associated polynomial CRC function.
            crcfun = mkCrcFun(*crcfun_params)

            for msg in self.test_messages:
                self.assertEqual(crcfun(msg), crc_poly_fun(msg))



def runtests():    print "Using extension:", _usingExtension
    print
    unittest.main()if __name__ == '__main__':
    runtests()