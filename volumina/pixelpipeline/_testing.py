try:
    import lazyflow
    has_lazyflow = True
except ImportError:
    has_lazyflow = False

if has_lazyflow:
    from lazyflow.graph import Operator, InputSlot, OutputSlot
    from lazyflow import operators
    import time

#*******************************************************************************
# O p D e l a y                                                                *
#*******************************************************************************

    class OpDelay(operators.OpArrayPiper):
        def __init__( self, g, delay_factor = 0.000001 ):
            super(OpDelay, self).__init__(g)
            self._delay_factor = delay_factor

        def execute(self, slot, roi, resultArea):
            key = roi.toSlice()
            req = self.inputs["Input"][key].writeInto(resultArea)
            req.wait()
            t = self._delay_factor*resultArea.nbytes
            print "Delay: " + str(t) + " secs."
            time.sleep(t)
            return resultArea

#*******************************************************************************
# O p D a t a P r o v i d e r                                                  *
#*******************************************************************************

    class OpDataProvider(Operator):
        name = "Data Provider"
        category = "Input"

        inputSlots = [InputSlot("Changedata")]
        outputSlots = [OutputSlot("Data")]

        def __init__(self, g, data):
            Operator.__init__(self,g)
            self._data = data
            oslot = self.outputs["Data"]
            oslot._shape = self._data.shape
            oslot._dtype = self._data.dtype

        def execute(self, slot, roi, result):
            key = roi.toSlice()
            result[:] = self._data[key]
            return result

        def setInSlot(self, slot, key, value):
            self._data[key] = value
            self.outputs["Output"].setDirty(key)
