"""
This application shows a mesh using Mayavi as a component of a large Qt application.
"""

import os
os.environ['ETS_TOOLKIT'] = 'qt4'

# To be able to use PySide or PyQt4 and not run in conflicts with traits,
# we need to import QtGui and QtCore from pyface.qt
from pyface.qt import QtGui, QtCore

from mayavi import mlab
from traits.api import HasTraits, Instance, on_trait_change
from traitsui.api import View, Item
from mayavi.core.ui.api import MlabSceneModel, SceneEditor
from tvtk.pyface.api import Scene

from PySide import QtUiTools, QtCore, QtGui

import numpy as np

from mlabplot import MPlot3D
from robpath import RobPath


class Visualization(HasTraits):
    scene = Instance(MlabSceneModel, ())

    @on_trait_change('scene.activated')
    def update_plot(self):
        # This function is called when the view is opened.
        self.scene.mlab.view(0, 65, 150)
        self.scene.background = (0.2, 0.2, 0.2)
        pass

    # the layout of the dialog screated
    view = View(Item('scene', editor=SceneEditor(scene_class=Scene),
                     height=600, width=800, show_label=False), resizable=True)


class QMayavi(QtGui.QWidget):
    def __init__(self, parent=None):
        super(QMayavi, self).__init__(parent)

        self.setWindowTitle("Mesh Viewer")
        layout = QtGui.QGridLayout(self)
        layout.setSpacing(3)

        ui_mlab = Visualization().edit_traits(parent=self, kind='subpanel').control
        layout.addWidget(ui_mlab, 0, 0)
        self.mlab = MPlot3D(mlab=True)

        self.progress = QtGui.QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setTextVisible(False)
        self.progress.setMinimumHeight(6)
        self.progress.setMaximumHeight(6)
        layout.addWidget(self.progress, 1, 0)

    def drawWorkingArea(self, width=300, height=200):
        self.mlab.clear()
        self.mlab.draw_working_area(width, height)
        self.mlab.draw_points(np.float32([[0, 0, 0], [height, width, 50]]), scale=0.1) # working area
        self.mlab.outline()

    def drawMesh(self, mesh):
        self.drawWorkingArea()
        self.mlab.draw_mesh(mesh)

    def drawSlice(self, slices, path):
        self.mlab.draw_slice(slices[-1])
        #self.plot.mlab.draw_path(tool_path)
        self.mlab.draw_path(path)


class RobPathUI(QtGui.QMainWindow):
    def __init__(self):
        super(RobPathUI, self).__init__()
        self.Window = QtUiTools.QUiLoader().load('robpath.ui')

        self.plot = QMayavi()
        self.Window.boxPlot.addWidget(self.plot)
        self.plot.drawWorkingArea()

        self.Window.btnLoadMesh.clicked.connect(self.btnLoadMeshClicked)
        self.Window.btnProcessMesh.clicked.connect(self.btnProcessMeshClicked)
        self.Window.btnSaveRapid.clicked.connect(self.btnSaveRapidClicked)

        self.Window.sbPositionX.valueChanged.connect(self.changePosition)
        self.Window.sbPositionY.valueChanged.connect(self.changePosition)
        self.Window.sbPositionZ.valueChanged.connect(self.changePosition)

        self.Window.sbSizeX.valueChanged.connect(self.changeSize)
        self.Window.sbSizeY.valueChanged.connect(self.changeSize)
        self.Window.sbSizeZ.valueChanged.connect(self.changeSize)

        self.Window.btnQuit.clicked.connect(self.btnQuitClicked)

        self.processing = False
        self.timer = QtCore.QTimer(self.plot)
        self.timer.timeout.connect(self.updateProcess)

        self.robpath = RobPath()

    def changePosition(self):
        x = self.Window.sbPositionX.value()
        y = self.Window.sbPositionY.value()
        z = self.Window.sbPositionZ.value()
        self.robpath.translate_mesh(np.float32([x, y, z]))
        self.plot.drawMesh(self.robpath.mesh)

    def changeSize(self):
        sx = self.Window.sbSizeX.value() + 0.00001
        sy = self.Window.sbSizeY.value() + 0.00001
        sz = self.Window.sbSizeZ.value() + 0.00001
        self.robpath.resize_mesh(np.float32([sx, sy, sz]))
        self.changePosition()

    def updatePosition(self, position):
        x, y, z = position
        self.Window.sbPositionX.setValue(x)
        self.Window.sbPositionY.setValue(y)
        self.Window.sbPositionZ.setValue(z)

    def updateSize(self, size):
        sx, sy, sz = size
        self.Window.sbSizeX.setValue(sx)
        self.Window.sbSizeY.setValue(sy)
        self.Window.sbSizeZ.setValue(sz)

    def updateProcess(self):
        if self.robpath.k < len(self.robpath.levels):
            self.robpath.update_process()
            self.plot.drawSlice(self.robpath.slices, self.robpath.path)
            self.plot.progress.setValue(100.0 * self.robpath.k / len(self.robpath.levels))
        else:
            self.processing = False
            self.timer.stop()

    def blockSignals(self, value):
        self.Window.sbPositionX.blockSignals(value)
        self.Window.sbPositionY.blockSignals(value)
        self.Window.sbPositionZ.blockSignals(value)
        self.Window.sbSizeX.blockSignals(value)
        self.Window.sbSizeY.blockSignals(value)
        self.Window.sbSizeZ.blockSignals(value)

    def btnLoadMeshClicked(self):
        self.blockSignals(True)
        try:
            filename = QtGui.QFileDialog.getOpenFileName(self.plot, 'Open file', './',
                                                         'Mesh Files (*.stl)')[0]
            self.Window.setWindowTitle('Mesh Viewer: %s' %filename)
            self.robpath.load_mesh(filename)
            # -----
            # TODO: Change bpoints.
            self.updatePosition(self.robpath.mesh.bpoint1) # Rename to position
            self.updateSize(self.robpath.mesh.bpoint2 - self.robpath.mesh.bpoint1) # Change by size
            self.Window.lblInfo.setText('Info:\n')
            # -----
            self.plot.drawMesh(self.robpath.mesh)
        except:
            pass
        self.blockSignals(False)

    def btnProcessMeshClicked(self):
        if self.processing:
            self.timer.stop()
            self.processing = False
        else:
            self.plot.drawWorkingArea()

            height = self.Window.sbHeight.value() + 0.00001
            width = self.Window.sbWidth.value() + 0.00001
            overlap = 0.01 * self.Window.sbOverlap.value()
            self.robpath.set_track(height, width, overlap)
            speed = self.Window.sbSpeed.value()
            self.robpath.set_speed(speed)
            power = self.Window.sbPower.value()
            self.robpath.set_power(power)

            self.robpath.init_process()

            self.processing = True
            self.timer.start(100)

    def btnSaveRapidClicked(self):
        #filename = QtGui.QFileDialog.getOpenFileName(self.plot, 'Save file', './',
        #                                             'Rapid Modules (*.mod)')[0]
        self.robpath.save_rapid()

    def btnQuitClicked(self):
        QtCore.QCoreApplication.instance().quit()



if __name__ == "__main__":
    # Don't create a new QApplication, it would unhook the Events
    # set by Traits on the existing QApplication. Simply use the
    # '.instance()' method to retrieve the existing one.
    app = QtGui.QApplication.instance()
    robpath = RobPathUI()
    robpath.Window.show()
    app.exec_()

