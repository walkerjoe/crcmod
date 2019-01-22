try:
    from crcmod.crcmod import _usingExtension
    from crcmod.crcmod import *
    import crcmod.predefined
except ImportError:
    from crcmod import *
    import predefined
__doc__ = crcmod.__doc__
