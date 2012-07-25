#!/usr/bin/env python
from PyQt4.QtCore import Qt, QTimer, QRectF
from PyQt4.QtGui import QApplication, QWidget, QShortcut, QKeySequence, \
                        QSplitter, QVBoxLayout, QHBoxLayout, QPushButton, \
                        QColor, QSizePolicy, QAction, QIcon

import numpy, copy
from functools import partial

from quadsplitter import QuadView
      
from sliceSelectorHud import ImageView2DHud, QuadStatusBar
from pixelpipeline.datasources import ArraySource, LazyflowSinkSource

from volumeEditor import VolumeEditor
import volumina.icons_rc

#*******************************************************************************
# V o l u m e E d i t o r W i d g e t                                          *
#*******************************************************************************

class ImageEditorWidget(QWidget):
    def __init__( self, parent=None, editor=None ):
        super(ImageEditorWidget, self).__init__(parent=parent)
        
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setFocusPolicy(Qt.StrongFocus)
        
        self.editor = None
        if editor!=None:
            self.init(editor)

        self.allZoomToFit = QAction(QIcon(":/icons/icons/view-fullscreen.png"), "Zoom to &Fit", self)
        self.allZoomToFit.triggered.connect(self._fitToScreen)

        self.allToggleHUD = QAction(QIcon(), "Show &HUDs", self)
        self.allToggleHUD.setCheckable(True)
        self.allToggleHUD.setChecked(True)
        self.allToggleHUD.toggled.connect(self._toggleHUDs)

        self.allCenter = QAction(QIcon(), "&Center views", self)
        self.allCenter.triggered.connect(self._centerAllImages)

        self.selectedCenter = QAction(QIcon(), "C&enter view", self)
        self.selectedCenter.triggered.connect(self._centerImage)

        self.selectedZoomToFit = QAction(QIcon(":/icons/icons/view-fullscreen.png"), "Zoom to Fit", self)
        self.selectedZoomToFit.triggered.connect(self._fitImage)

        self.selectedZoomToOriginal = QAction(QIcon(), "Reset Zoom", self)
        self.selectedZoomToOriginal.triggered.connect(self._restoreImageToOriginalSize)

        self.rubberBandZoom = QAction(QIcon(), "Rubberband Zoom", self)
        self.rubberBandZoom.triggered.connect(self._rubberBandZoom)

        self.toggleSelectedHUD = QAction(QIcon(), "Show HUD", self)
        self.toggleSelectedHUD.setCheckable(True)
        self.toggleSelectedHUD.setChecked(True)
        self.toggleSelectedHUD.toggled.connect(self._toggleSelectedHud)



    def _setupVolumeExtent( self ):
        '''Setup min/max values of position/coordinate control elements.

        Position/coordinate information is read from the volumeEditor's positionModel.

        '''
        self.quadview.statusBar.channelSpinBox.setRange(0,self.editor.posModel.shape5D[-1] - 1)
        self.quadview.statusBar.timeSpinBox.setRange(0,self.editor.posModel.shape5D[0] - 1)
        
        for i in range(3):
            self.editor.imageViews[i].hud.setMaximum(self.editor.posModel.volumeExtent(i)-1)
    
    def init(self, volumina):
        self.editor = volumina

        def onViewFocused():
            axis = self.editor._lastImageViewFocus;
            self.toggleSelectedHUD.setChecked( self.editor.imageViews[axis]._hud.isVisible() )
        self.editor.newImageView2DFocus.connect(onViewFocused)

        self.layout = QHBoxLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        self.setLayout(self.layout)
        
        # setup quadview
        axisLabels = ["X", "Y", "Z"]
        axisColors = [QColor("#dc143c"), QColor("green"), QColor("blue")]
        for i, v in enumerate(self.editor.imageViews):
            v.hud = ImageView2DHud()
            #connect interpreter
            v.hud.createImageView2DHud(axisLabels[i], 0, axisColors[i], QColor("white"))
            v.hud.sliceSelector.valueChanged.connect(partial(self.editor.navCtrl.changeSliceAbsolute, axis=i))

        self.quadview = QuadView(self, self.editor.imageViews[2], self.editor.imageViews[0], self.editor.imageViews[1], self.editor.view3d)
        
        #hide and disable unnecessary views
        self.quadview.dock2_ofSplitHorizontal1.hide()
        self.quadview.splitHorizontal2.hide()
        
        #modify the remaining view
        self.quadview.dock1_ofSplitHorizontal1.graphicsView._hud.maxButton.hide()
        self.quadview.dock1_ofSplitHorizontal1.graphicsView._hud.dockButton.hide()
        self.quadview.dock1_ofSplitHorizontal1.graphicsView._hud.axisLabel.hide()
        self.quadview.dock1_ofSplitHorizontal1.graphicsView._hud.sliceSelector.spinBox.hide()
        self.quadview.dock1_ofSplitHorizontal1.graphicsView._hud.sliceSelector.downLabel.hide()
        self.quadview.dock1_ofSplitHorizontal1.graphicsView._hud.sliceSelector.upLabel.hide()
        self.quadview.dock1_ofSplitHorizontal1.graphicsView._sliceIntersectionMarker.setVisibility(False)
        
        self.quadViewStatusBar = QuadStatusBar()
        self.quadViewStatusBar.createQuadViewStatusBar(QColor("#dc143c"), QColor("white"), QColor("green"), QColor("white"), QColor("blue"), QColor("white"), QColor("gray"), QColor("white"))
        #reconfigure StatusBar
        self.quadViewStatusBar.zLabel.hide()
        self.quadViewStatusBar.zSpinBox.hide()
        self.quadViewStatusBar.positionCheckBox.setChecked(False)
        self.quadViewStatusBar.positionCheckBox.hide()
        
        self.quadview.addStatusBar(self.quadViewStatusBar)
        self.layout.addWidget(self.quadview)

        def setChannel(c):
            print "set channel = %d, posModel has channel = %d" % (c, self.editor.posModel.channel)
            if c == self.editor.posModel.channel:
                return
            self.editor.posModel.channel = c
        self.quadview.statusBar.channelSpinBox.valueChanged.connect(setChannel)
        def getChannel(newC):
            self.quadview.statusBar.channelSpinBox.setValue(newC)
        self.editor.posModel.channelChanged.connect(getChannel)
        def setTime(t):
            print "set channel = %d, posModel has time = %d" % (t, self.editor.posModel.time)
            if t == self.editor.posModel.time:
                return
            self.editor.posModel.time = t
        self.quadview.statusBar.timeSpinBox.valueChanged.connect(setTime)
        def getTime(newT):
            self.quadview.statusBar.timeSpinBox.setValue(newT)
        self.editor.posModel.timeChanged.connect(getTime) 


        def toggleSliceIntersection(state):
            self.editor.navCtrl.indicateSliceIntersection = (state == Qt.Checked)
        self.quadview.statusBar.positionCheckBox.stateChanged.connect(toggleSliceIntersection)

        self.editor.posModel.cursorPositionChanged.connect(self._updateInfoLabels)

        # shortcuts
        self._initShortcuts()

        def onShapeChanged():
            self._setupVolumeExtent()

        self.editor.shapeChanged.connect(onShapeChanged)
        
        self.updateGeometry()
        self.update()
        self.quadview.update()
        
    def _toggleDebugPatches(self,show):
        self.editor.showDebugPatches = show

    def _fitToScreen(self):
        shape = self.editor.posModel.shape
        for i, v in enumerate(self.editor.imageViews):
            s = list(copy.copy(shape))
            del s[i]
            v.changeViewPort(v.scene().data2scene.mapRect(QRectF(0,0,*s)))  
            
    def _fitImage(self):
        if self.editor._lastImageViewFocus is not None:
            self.editor.imageViews[self.editor._lastImageViewFocus].fitImage()
            
    def _restoreImageToOriginalSize(self):
        if self.editor._lastImageViewFocus is not None:
            self.editor.imageViews[self.editor._lastImageViewFocus].doScaleTo()
                
    def _rubberBandZoom(self):
        if self.editor._lastImageViewFocus is not None:
            if not self.editor.imageViews[self.editor._lastImageViewFocus]._isRubberBandZoom:
                self.editor.imageViews[self.editor._lastImageViewFocus]._isRubberBandZoom = True
                self.editor.imageViews[self.editor._lastImageViewFocus]._cursorBackup = self.editor.imageViews[self.editor._lastImageViewFocus].cursor()
                self.editor.imageViews[self.editor._lastImageViewFocus].setCursor(Qt.CrossCursor)
            else:
                self.editor.imageViews[self.editor._lastImageViewFocus]._isRubberBandZoom = False
                self.editor.imageViews[self.editor._lastImageViewFocus].setCursor(self.editor.imageViews[self.editor._lastImageViewFocus]._cursorBackup)
            
    
    def _toggleHUDs(self, checked):
        for i, v in enumerate(self.editor.imageViews):
            v.setHudVisible(checked)
            
    def _toggleSelectedHud(self, checked):
        if self.editor._lastImageViewFocus is not None:
            self.editor.imageViews[self.editor._lastImageViewFocus].setHudVisible(checked)
            
    def _centerAllImages(self):
        for i, v in enumerate(self.editor.imageViews):
            v.centerImage()
            
    def _centerImage(self):
        if self.editor._lastImageViewFocus is not None:
            self.editor.imageViews[self.editor._lastImageViewFocus].centerImage()

    def _shortcutHelper(self, keySequence, group, description, parent, function, context = None, enabled = None):
        shortcut = QShortcut(QKeySequence(keySequence), parent, member=function, ambiguousMember=function)
        if context != None:
            shortcut.setContext(context)
        if enabled != None:
            shortcut.setEnabled(True)
        return shortcut, group, description

    def _initShortcuts(self):
        self.shortcuts = []
        #self.shortcuts.append(self._shortcutHelper("Ctrl+Z", "Labeling", "History undo", self, self.editor.historyUndo, Qt.ApplicationShortcut, True))
        #self.shortcuts.append(self._shortcutHelper("Ctrl+Shift+Z", "Labeling", "History redo", self, self.editor.historyRedo, Qt.ApplicationShortcut, True))
        #self.shortcuts.append(self._shortcutHelper("Ctrl+Y", "Labeling", "History redo", self, self.editor.historyRedo, Qt.ApplicationShortcut, True))
        
        def fullscreenView(axis):
            m = not self.quadview.maximized
            print "maximize axis=%d = %r" % (axis, m)
            self.quadview.setMaximized(m, axis)
        
        maximizeShortcuts = ['x', 'y', 'z']
        maximizeViews     = [1,   2,     0]
        for i, v in enumerate(self.editor.imageViews):
            self.shortcuts.append(self._shortcutHelper(maximizeShortcuts[i], "Navigation", \
                                  "Enlarge slice view %s to full size" % maximizeShortcuts[i], \
                                  self, partial(fullscreenView, maximizeViews[i]), Qt.WidgetShortcut))
            
            #self.shortcuts.append(self._shortcutHelper("n", "Labeling", "Increase brush size", v,self.editor._drawManager.brushSmaller, Qt.WidgetShortcut))
            #self.shortcuts.append(self._shortcutHelper("m", "Labeling", "Decrease brush size", v, self.editor._drawManager.brushBigger, Qt.WidgetShortcut))
            self.shortcuts.append(self._shortcutHelper("+", "Navigation", "Zoom in", v,  v.zoomIn, Qt.WidgetShortcut))
            self.shortcuts.append(self._shortcutHelper("-", "Navigation", "Zoom out", v, v.zoomOut, Qt.WidgetShortcut))
            
            self.shortcuts.append(self._shortcutHelper("c", "Navigation", "Center image", v,  v.centerImage, Qt.WidgetShortcut))
            self.shortcuts.append(self._shortcutHelper("h", "Navigation", "Toggle hud", v,  v.toggleHud, Qt.WidgetShortcut))
            
            self.shortcuts.append(self._shortcutHelper("q", "Navigation", "Switch to next channel",     v, self.editor.nextChannel,     Qt.WidgetShortcut))
            self.shortcuts.append(self._shortcutHelper("a", "Navigation", "Switch to previous channel", v, self.editor.previousChannel, Qt.WidgetShortcut))
            
            def sliceDelta(axis, delta):
                newPos = copy.copy(self.editor.posModel.slicingPos)
                newPos[axis] += delta
                self.editor.posModel.slicingPos = newPos
            self.shortcuts.append(self._shortcutHelper("p", "Navigation", "Slice up",   v, partial(sliceDelta, i, 1),  Qt.WidgetShortcut))
            self.shortcuts.append(self._shortcutHelper("o", "Navigation", "Slice down", v, partial(sliceDelta, i, -1), Qt.WidgetShortcut))
            
            self.shortcuts.append(self._shortcutHelper("Ctrl+Up",   "Navigation", "Slice up",   v, partial(sliceDelta, i, 1),  Qt.WidgetShortcut))
            self.shortcuts.append(self._shortcutHelper("Ctrl+Down", "Navigation", "Slice down", v, partial(sliceDelta, i, -1), Qt.WidgetShortcut))
            
            self.shortcuts.append(self._shortcutHelper("Ctrl+Shift+Up",   "Navigation", "10 slices up",   v, partial(sliceDelta, i, 10),  Qt.WidgetShortcut))
            self.shortcuts.append(self._shortcutHelper("Ctrl+Shift+Down", "Navigation", "10 slices down", v, partial(sliceDelta, i, -10), Qt.WidgetShortcut))

    def _updateInfoLabels(self, pos):
        self.quadViewStatusBar.setMouseCoords(*pos)
             
#*******************************************************************************
# i f   _ _ n a m e _ _   = =   " _ _ m a i n _ _ "                            *
#*******************************************************************************
if __name__ == "__main__":
    
    import sys
    from layerstack import LayerStackModel
    from volumina.layer import GrayscaleLayer
    from volumina.pixelpipeline.datasources import ArraySource
    
    array = numpy.random.rand(10,400,400,400,1)
    array *= 255
    array = array.astype('uint8')
    
    layer = GrayscaleLayer(ArraySource(array))
    app = QApplication(sys.argv)
    layerStackModel = LayerStackModel()
    layerStackModel.insert(0,layer)
    volumeEditor = VolumeEditor(layerStackModel)
    volumeEditor.dataShape = array.shape
    imageEditorWidget = ImageEditorWidget(editor=volumeEditor)
    imageEditorWidget.show()
    app.exec_()
    