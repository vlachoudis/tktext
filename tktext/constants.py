#
# -*- coding: utf-8 -*-
#
# Copyright European Organization for Nuclear Research (CERN)
# All rights reserved
#
# Please look at the supplied documentation for the user's
# license
#
# Author: Vasilis.Vlachoudis@cern.ch
# Date:   12-Nov-2026

"""constants — tkinter.constants."""
import tktext as _pkg

globals().update({n: getattr(_pkg, n) for n in _pkg._CONSTANT_NAMES})
