###############################################################################
#   volumina: volume slicing and editing library
#
#       Copyright (C) 2011-2014, the ilastik developers
#                                <team@ilastik.org>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the Lesser GNU General Public License
# as published by the Free Software Foundation; either version 2.1
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Lesser General Public License for more details.
#
# See the files LICENSE.lgpl2 and LICENSE.lgpl3 for full text of the
# GNU Lesser General Public License version 2.1 and 3 respectively.
# This information is also available on the ilastik web site at:
# 		   http://ilastik.org/license/
###############################################################################
from builtins import object
import unittest as ut
import os
from abc import ABCMeta, abstractmethod
import volumina._testing
from volumina.pixelpipeline.datasources import ArraySource, RelabelingArraySource
import numpy as np
from volumina.slicingtools import sl, slicing2shape
from future.utils import with_metaclass

try:
    import lazyflow

    has_lazyflow = True
except ImportError:
    has_lazyflow = False

if has_lazyflow:
    from lazyflow.graph import Graph
    from volumina.pixelpipeline._testing import OpDataProvider
    from volumina.pixelpipeline.datasources import LazyflowSource, LazyflowSinkSource


class GenericArraySourceTest(with_metaclass(ABCMeta, object)):
    @abstractmethod
    def setUp(self):
        self.slicing = (slice(0, 1), slice(10, 20), slice(20, 25), slice(0, 1), slice(0, 1))
        self.source = None

    def testRequestWait(self):
        slicing = self.slicing
        requested = self.source.request(slicing).wait()
        self.assertTrue(np.all(requested == self.raw[slicing]))

    def testSetDirty(self):
        self.signal_emitted = False

        def slot(sl):
            self.signal_emitted = True
            self.assertTrue(sl == self.slicing)

        self.source.isDirty.connect(slot)
        self.source.setDirty(self.slicing)
        self.source.isDirty.disconnect(slot)

        self.assertTrue(self.signal_emitted)

        del self.signal_emitted
        del self.slicing

    def testComparison(self):
        assert self.samesource == self.source
        assert self.othersource != self.source


class ArraySourceTest(ut.TestCase, GenericArraySourceTest):
    def setUp(self):
        GenericArraySourceTest.setUp(self)
        self.cells2d = np.load(os.path.join(volumina._testing.__path__[0], "2d_cells_apoptotic_1channel.npy"))
        y, x = self.cells2d.shape
        self.raw = np.zeros((1, y, x, 1, 1))
        self.raw[0, :, :, 0, 0] = self.cells2d
        self.source = ArraySource(self.raw)

        self.samesource = ArraySource(self.raw)
        self.othersource = ArraySource(np.array(self.raw))


class RelabelingArraySourceTest(ut.TestCase, GenericArraySourceTest):
    def setUp(self):
        GenericArraySourceTest.setUp(self)
        a = np.zeros((5, 1, 1, 1, 1), dtype=np.uint32)
        # the data contained in a ranges from [1,5]
        a[:, 0, 0, 0, 0] = np.arange(0, 5)
        self.source = RelabelingArraySource(a)

        # we apply the relabeling i -> i+1
        relabeling = np.arange(1, a.max() + 2, dtype=np.uint32)
        self.source.setRelabeling(relabeling)

        self.samesource = RelabelingArraySource(a)
        self.othersource = RelabelingArraySource(np.array(a))

    def testRequestWait(self):
        slicing = (slice(0, 5), slice(None), slice(None), slice(None), slice(None))
        requested = self.source.request(slicing).wait()
        assert requested.ndim == 5
        self.assertTrue(np.all(requested.flatten() == np.arange(1, 6, dtype=np.uint32)))

    def testSetDirty(self):
        self.signal_emitted = False
        self.slicing = (slice(0, 5), slice(None), slice(None), slice(None), slice(None))

        def slot(sl):
            self.signal_emitted = True
            self.assertTrue(sl == self.slicing)

        self.source.isDirty.connect(slot)
        self.source.setDirty(self.slicing)
        self.source.isDirty.disconnect(slot)

        self.assertTrue(self.signal_emitted)

        del self.signal_emitted
        del self.slicing


if __name__ == "__main__":
    ut.main()
