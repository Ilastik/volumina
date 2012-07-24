from functools import partial
from PyQt4.QtCore import QObject, pyqtSignal, QRect
from slicesources import SliceSource, SyncedSliceSources
from imagesourcefactories import createImageSource
from volumina.pixelpipeline.imagesources import AlphaModulatedImageSource, ColortableImageSource

class StackedImageSources( QObject ):
    """
    Manages an ordered stack of image sources.
    
    The StackedImageSources manages the 'add' and 'remove' operation to a stack
    of objects derived from 'ImageSource'. The stacking order mirrors the
    LayerStackModel, and each Layer object has a corresponding ImageSource
    object that can be queried to produce images which adhere to the
    specification as defined in the Layer object. 

    Imagesource indices in the stack correspond to row numbers. So the
    topmost imagesource has an index 0, the second-to-the-top an index
    of 1 and so on. This is different from other stacks, where the
    bottommost item has the lowest index.

    Layers from the underlying layerstack have to be registered
    explicitly to become active in the StackedImageSources. If
    registered layers are removed in the underlying layerstack they
    are automatically deregistered.

    """    
    layerDirty = pyqtSignal(object, object)
    visibleChanged = pyqtSignal(object, bool)
    opacityChanged = pyqtSignal(object, float)
    sizeChanged  = pyqtSignal()
    orderChanged = pyqtSignal()
    stackIdChanged = pyqtSignal( object, object ) # old id, new id
    layerIdChanged = pyqtSignal( object, object, object ) # ims, old id, new id

    @property
    def stackId( self ):
        return self._stackId

    @stackId.setter
    def stackId( self, v ):
        old = self._stackId
        self._stackId = v
        self.stackIdChanged.emit( old, v )

    class _ViewBase( object ):
        def __init__( self, sims ):
            self.sims = sims

        def __len__( self ):
            return len(self.sims)

    class VisibleView( _ViewBase ):
        def __iter__( self ):
            return ( layer.visible
                     for layer in self.sims._layerStackModel
                     if self.sims.isRegistered(layer)  )

        def __getitem__( self, row ):
            return self.sims._getLayer(row).visible

    class OccludedView( _ViewBase ):
        def __iter__( self ):
            return ( self.sims._imsOccluded[self.sims._layerToIms[layer]]
                     for layer in self.sims._layerStackModel
                     if self.sims.isRegistered(layer) )

        def __getitem__( self, row ):
            return self.sims._imsOccluded[self.sims._layerToIms[self.sims._getLayer(row)]]

    class OpacityView( _ViewBase ):
        def __iter__( self ):
            return ( layer.opacity
                     for layer in self.sims._layerStackModel
                     if self.sims.isRegistered(layer) )

        def __getitem__( self, row ):
            return self.sims._getLayer(row).opacity

    class ImageSourceView( _ViewBase ):
        def __iter__( self ):
            return ( self.sims._layerToIms[layer]
                     for layer in self.sims._layerStackModel
                     if self.sims.isRegistered(layer) )

        def __getitem__( self, row ):
            return self.sims._layerToIms[self.sims._getLayer(row)]

    def __init__( self, layerStackModel ):
        super(StackedImageSources, self).__init__()
        self._layerStackModel = layerStackModel

        # we need to store partial functions to which we connect
        # for later disconnection
        self._curryRegistry = {'I':{}, "O":{}, "V":{}, "Id":{}}

        # Each layer has a single image source, which has been set-up according
        # to the layer's specification.
        # Note, that we don't maintain our own imagesource stack. We just observe
        # the layerStackModel and mirror the stack order there
        self._layerToIms = {} #look up layer -> corresponding image source
        self._imsToLayer = {} #look up image source -> corresponding layer
        self._imsOccluded = {}
        self._firstOpaqueIdx = None

        layerStackModel.orderChanged.connect( self._onOrderChanged )
        layerStackModel.layerRemoved.connect( self._onLayerRemoved )

        self._stackId = 0

    def __len__( self ):
        return len([ _ for _ in self])

    def __getitem__(self, row):
        layer = self._getLayer(row)
        ims = self._layerToIms[layer]
        return (layer.visible, layer.opacity, ims)

    def __iter__( self ):
        return ( (layer.visible, layer.opacity, self._layerToIms[layer])
                 for layer in self._layerStackModel
                 if layer in self._layerToIms.keys() )
                
    def __reversed__( self ):
        return ( (layer.visible, layer.opacity, self._layerToIms[layer])
                 for layer in reversed(self._layerStackModel)
                 if self.isRegistered(layer) )

    def getVisible( self, row ):
        return self._getLayer(row).visible

    def getOpacity( self, row ):
        return self._getLayer(row).opacity

    def getImageSource( self, row ):
        return self._layerToIms[self._getLayer(row)]

    def viewVisible( self ):
        return StackedImageSources.VisibleView( self )

    def viewOccluded( self ):
        return StackedImageSources.OccludedView( self )

    def viewOpacity( self ):
        return StackedImageSources.OpacityView( self )

    def viewImageSources( self ):
        return StackedImageSources.ImageSourceView( self )

    def register( self, layer, imageSource ):
        if self.isRegistered(layer):
            raise Exception("StackedImageSources.register(): layer %s already registered" % str(layer))
        if layer not in self._layerStackModel:
            raise Exception("StackedImageSources.register(): layer %s is not in LayerStackModel" % str(layer))
        self._layerToIms[layer] = imageSource
        self._imsToLayer[imageSource] = layer

        self._curryRegistry['I'][imageSource] = partial(self._onImageSourceDirty, imageSource)
        self._curryRegistry['O'][layer] = partial(self._onOpacityChanged, layer)
        self._curryRegistry['V'][layer] = partial(self._onVisibleChanged, layer)
        self._curryRegistry['Id'][imageSource] = partial(self._onImageSourceIdChanged, imageSource)

        imageSource.isDirty.connect( self._curryRegistry['I'][imageSource] ) 
        layer.opacityChanged.connect( self._curryRegistry['O'][layer] )
        layer.visibleChanged.connect( self._curryRegistry['V'][layer] )
        imageSource.idChanged.connect( self._curryRegistry['Id'][imageSource] )

        self._updateOcclusionInfo()
        self.sizeChanged.emit()

    def deregister( self, layer ):
        self._removeLayer( layer )
        self.sizeChanged.emit()

    def clear( self ):
        all_layers = self.getRegisteredLayers()
        map( self._removeLayer, all_layers )
        assert( len(self) == 0 )
        assert( len(self.getRegisteredLayers() ) == 0 )
        self.sizeChanged.emit()

    def getRegisteredLayers( self ):
        return self._layerToIms.keys()

    def isRegistered( self, layer ):
        return layer in self._layerToIms

    def firstFullyOpaque(self):
        '''Return index of the first fully opaque imagesource.

        An imagesource is fully opaque when:
        * it is visible
        * its opacity is 1.0
        * the corresponding layer is opaque (i.e. there are
          no transparent 'holes' in the layer)
        
        '''
        return self._firstOpaqueIdx

    def isOccluded( self, ims ):
        '''Test if imagesource is below the first fully opaque layer.

        An occluded imagesource cannot be 'seen' when looking at the
        stack from 'above'. This property is useful to tune the image
        rendering.
        
        '''
        return self._imsOccluded[ims]

    def isVisible( self, ims ):
        if self.isRegistered(self._imsToLayer[ims]):
            return self._imsToLayer[ims].visible
        else:
            raise KeyError()

    def _onImageSourceDirty( self, imageSource, rect ):
        self.layerDirty.emit( imageSource, rect )

    def _onImageSourceIdChanged( self, imageSource, oldId, newId ):
        self.layerIdChanged.emit( imageSource, oldId, newId )

    def _onOpacityChanged( self, layer, opacity ):
        self._updateOcclusionInfo()
        self.opacityChanged.emit(self._layerToIms[layer], opacity)

    def _onVisibleChanged( self, layer, visible ):
        self._updateOcclusionInfo()
        self.visibleChanged.emit(self._layerToIms[layer], visible)

    def _onOrderChanged( self ):
        self._updateOcclusionInfo()
        self.orderChanged.emit()

    def _onLayerRemoved( self, layer, row ):
        if self.isRegistered( layer ):
            self.deregister( layer )
            assert(not self.isRegistered( layer ))

    def _getLayer( self, ims_row ):
        return [layer for layer in self._layerStackModel
                       if self.isRegistered(layer)][ims_row]

    def _removeLayer( self, layer ):
        if layer not in self._layerToIms:
            raise Exception("StackedImageSources._removeLayer(): layer %s is not registered; can't be removed" % str(layer))
        ims = self._layerToIms[layer]

        ims.isDirty.disconnect( self._curryRegistry['I'][ims] )
        layer.opacityChanged.disconnect( self._curryRegistry['O'][layer] )
        layer.visibleChanged.disconnect( self._curryRegistry['V'][layer] )
        ims.idChanged.disconnect( self._curryRegistry['Id'][ims] )
        
        del self._curryRegistry['I'][ims]
        del self._curryRegistry['O'][layer]
        del self._curryRegistry['V'][layer]
        del self._curryRegistry['Id'][ims]

        del self._imsToLayer[ims]
        del self._layerToIms[layer]

        self._updateOcclusionInfo()

    def _updateOcclusionInfo(self):
        self._firstOpaqueIdx = None
        self._imsOccluded = {}

        # Search for the first totally opaque and visible layer (if any)
        for i, v in enumerate( self ):
            if (v[0] # visible
            and v[1] == 1.0 # opacity
            and v[2].isOpaque()): # ims guarantees opaqueness
                self._firstOpaqueIdx = i
                break

        for i, v in enumerate( self.viewImageSources() ):
            if self._firstOpaqueIdx != None and i > self._firstOpaqueIdx:
                self._imsOccluded[v] = True
            else:
                self._imsOccluded[v] = False


#*******************************************************************************
# I m a g e P u m p                                                            *
#*******************************************************************************

class ImagePump( object ):
    @property
    def syncedSliceSources( self ):
        return self._syncedSliceSources

    @property
    def stackedImageSources( self ):
        return self._stackedImageSources

    def __init__( self, layerStackModel, sliceProjection ):
        super(ImagePump, self).__init__()
        self._layerStackModel = layerStackModel
        self._projection = sliceProjection
        self._layerToSliceSrcs = {}
    
        ## setup image source stack and slice sources
        self._syncedSliceSources = SyncedSliceSources( len(sliceProjection.along) * (0,) )
        self._stackedImageSources = StackedImageSources( layerStackModel )
        for layer in self._layerStackModel:
            self._addLayer( layer )
        self._stackedImageSources.stackId = self._syncedSliceSources.id
        self._syncedSliceSources.idChanged.connect( self._onIdChanged )

        self._layerStackModel.layerAdded.connect( self._onLayerAdded )
        self._layerStackModel.layerRemoved.connect( self._onLayerRemoved )
        self._layerStackModel.stackCleared.connect( self._onStackCleared )

    def _onLayerAdded( self, layer, row ):
        self._addLayer( layer )

    def _onLayerRemoved( self, layer, row ):
        self._removeLayer( layer )

    def _onStackCleared( self ):
        self._stackedImageSources.clear()
        assert(len(self._stackedImageSources.getRegisteredLayers()) == 0)
        for layer, sss in self._layerToSliceSrcs.iteritems():
            for ss in sss:
                self._syncedSliceSources.remove(ss)
        assert(len(self._syncedSliceSources) == 0 )
        self._layerToSliceSrcs = {}

    def _onIdChanged( self, old, new ):
        self._stackedImageSources.stackId = new

    def _createSources( self, layer ):
        def sliceSrcOrNone( datasrc ):
            if datasrc:
                return SliceSource( datasrc, self._projection )
            return None

        slicesrcs = map( sliceSrcOrNone, layer.datasources )
        ims = createImageSource( layer, slicesrcs )
        # remove Nones
        slicesrcs = [ src for src in slicesrcs if src != None]
        return slicesrcs, ims

    def _addLayer( self, layer ):
        sliceSources, imageSource = self._createSources(layer)
        for ss in sliceSources:
            self._syncedSliceSources.add(ss)
        self._layerToSliceSrcs[layer] = sliceSources
        self._stackedImageSources.register(layer, imageSource)

    def _removeLayer( self, layer ):
        for ss in self._layerToSliceSrcs[layer]:
            self._syncedSliceSources.remove(ss)
        del self._layerToSliceSrcs[layer]

