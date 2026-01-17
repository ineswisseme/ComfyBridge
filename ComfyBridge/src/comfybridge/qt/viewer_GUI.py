# comfybridge/qt/viewer_GUI.py

import os
from pydoc import text
import numpy as np
import cv2
from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import QPainterPath, QImage, QPixmap, QPainter, QColor
from PySide6.QtWidgets import QMessageBox
from tomlkit import value

from comfybridge.core.io_utils import qimage_to_numpy, numpy_to_qimage
from comfybridge.core.maya_bridge import is_maya_running
from comfybridge.core.generate_model import generate_3d_model

# Image Viewer Widget

class ImageViewer(QtWidgets.QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.image_original = None

        self._scene = QtWidgets.QGraphicsScene(self)
        self.setScene(self._scene)

        self.pixmap_item = None
        self.image = None
        self.mask = None

        self.mode = "pan"
        self._panning = False
        self._last_pan = None

        self.lasso_path = QPainterPath()
        self.lasso_item = None
        self._overlay_item = None

        self.setRenderHints(QtGui.QPainter.Antialiasing |
                            QtGui.QPainter.SmoothPixmapTransform)

        self.setDragMode(QtWidgets.QGraphicsView.NoDrag)

    
    def load_image(self, path: str):
        if not os.path.isfile(path):
            raise FileNotFoundError(path)

        qimg = QImage(path)
        if qimg.isNull():
            raise RuntimeError(f"Failed to load {path}")

        self.image_original = qimg.convertToFormat(QImage.Format_RGBA8888)
        self.image = self.image_original.copy()

        if self.pixmap_item:
            self._scene.removeItem(self.pixmap_item)

        pix = QPixmap.fromImage(self.image)
        self.pixmap_item = self._scene.addPixmap(pix)
        self._scene.setSceneRect(QRectF(pix.rect()))

        self.fitInView(self._scene.sceneRect(), Qt.KeepAspectRatio)
        self.clear_selection()

    
    def wheelEvent(self, event):
        factor = 1.25 if event.angleDelta().y() > 0 else 0.8
        self.scale(factor, factor)

   
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.mode == "pan":
            self._panning = True
            self._last_pan = event.position()
            self.setCursor(Qt.ClosedHandCursor)
            return

        if event.button() == Qt.LeftButton and self.mode == "lasso":
            scene_pos = self.mapToScene(event.position().toPoint())
            self.lasso_path = QPainterPath()
            self.lasso_path.moveTo(scene_pos)

            if self.lasso_item:
                self._scene.removeItem(self.lasso_item)
                self.lasso_item = None
            return

        super().mousePressEvent(event)

    
    def mouseMoveEvent(self, event):
        if self._panning:
            delta = event.position() - self._last_pan
            self._last_pan = event.position()

            self.horizontalScrollBar().setValue(
                self.horizontalScrollBar().value() - delta.x()
            )
            self.verticalScrollBar().setValue(
                self.verticalScrollBar().value() - delta.y()
            )
            return

        if self.mode == "lasso" and (event.buttons() & Qt.LeftButton):
            scene_pos = self.mapToScene(event.position().toPoint())
            self.lasso_path.lineTo(scene_pos)

            if self.lasso_item:
                self._scene.removeItem(self.lasso_item)

            pen = QtGui.QPen(QColor(255, 200, 0, 200), 2)
            brush = QtGui.QBrush(QColor(255, 200, 0, 50))
            self.lasso_item = self._scene.addPath(self.lasso_path, pen, brush)
            return

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._panning:
            self._panning = False
            self.setCursor(Qt.ArrowCursor)
            return

        if event.button() == Qt.LeftButton and self.mode == "lasso":
            if not self.lasso_path.isEmpty():
                self._finalize_mask()
            return

        super().mouseReleaseEvent(event)


    def _finalize_mask(self):
        w, h = self.image.width(), self.image.height()
        mask_qimg = QImage(w, h, QImage.Format_Grayscale8)
        mask_qimg.fill(0)

        painter = QPainter(mask_qimg)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(Qt.white)
        painter.drawPath(self.lasso_path)
        painter.end()

        buf = qimage_to_numpy(mask_qimg)
        mask_np = buf[..., 0]

        self.mask = (mask_np > 127).astype(np.uint8) * 255
        self._update_overlay()

    def _update_overlay(self):
        if self._overlay_item:
            self._scene.removeItem(self._overlay_item)

        if self.mask is None:
            self._overlay_item = None
            return

        rgba = np.zeros((*self.mask.shape, 4), dtype=np.uint8)
        rgba[..., 1] = 180
        rgba[..., 2] = 255
        rgba[..., 3] = (self.mask > 0) * 120

        qimg = numpy_to_qimage(rgba)
        self._overlay_item = self._scene.addPixmap(QPixmap.fromImage(qimg))
        self._overlay_item.setZValue(1)

    
    def clear_selection(self):
        self.mask = None
        if self._overlay_item:
            self._scene.removeItem(self._overlay_item)
        if self.lasso_item:
            self._scene.removeItem(self.lasso_item)
        self._overlay_item = None
        self.lasso_item = None



# Main Window

class MainWindow(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ComfyBridge – Image Viewer")

        self.viewer = ImageViewer()
        
        # Progress Bar
        
        self.progress = QtWidgets.QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(True)
        self.progress.setFormat("Idle")
        self.progress.setFixedHeight(22)

        # UI buttons
        self.load_btn = QtWidgets.QPushButton("Load Image")
        self.load_btn.clicked.connect(self.on_load)

        self.pan_btn = QtWidgets.QPushButton("Pan")
        self.pan_btn.setCheckable(True)
        self.pan_btn.setChecked(True)
        self.pan_btn.clicked.connect(lambda: self.set_mode("pan"))

        self.lasso_btn = QtWidgets.QPushButton("Lasso")
        self.lasso_btn.setCheckable(True)
        self.lasso_btn.clicked.connect(lambda: self.set_mode("lasso"))

        self.clear_btn = QtWidgets.QPushButton("Clear")
        self.clear_btn.clicked.connect(self.viewer.clear_selection)

        self.gen_btn = QtWidgets.QPushButton("Generate Model")
        self.gen_btn.clicked.connect(self.on_generate)

        # Style for pressed buttons 
        style = """
            QPushButton { background-color: white; }
            QPushButton:checked { background-color: #888; color: white; }
        """
        self.pan_btn.setStyleSheet(style)
        self.lasso_btn.setStyleSheet(style)

        group = QtWidgets.QButtonGroup(self)
        group.addButton(self.pan_btn)
        group.addButton(self.lasso_btn)
        group.setExclusive(True)

        # Layout
        tools = QtWidgets.QVBoxLayout()
        tools.addWidget(self.load_btn)
        tools.addWidget(self.pan_btn)
        tools.addWidget(self.lasso_btn)
        tools.addWidget(self.clear_btn)
        tools.addSpacing(20)
        tools.addWidget(self.gen_btn)
        tools.addStretch()

        layout = QtWidgets.QHBoxLayout(self)
        layout.addLayout(tools)
        layout.addWidget(self.viewer)
        
        barpan = QtWidgets.QVBoxLayout()
        barpan.addWidget(self.viewer)
        barpan.addWidget(self.progress)  
        layout.addLayout(barpan)

        self.resize(1200, 800)

    def set_mode(self, mode):
        self.viewer.mode = mode
        self.viewer.setCursor(Qt.OpenHandCursor if mode == "pan" else Qt.CrossCursor)

 
    
    def update_progress(self, value, text): # update progress bar
        self.progress.setValue(value)
        self.progress.setFormat(text)
        QtWidgets.QApplication.processEvents()
        
        
    def on_load(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Load Image", "", "Images (*.png *.jpg *.jpeg *.bmp)"
        )
        if not path:
            return

        try:
            self.viewer.load_image(path)
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))


    def on_generate(self):
        if self.viewer.mask is None:
            QMessageBox.warning(self, "No Selection", "Please draw a lasso selection.")
            return

        # Always reset progress first
        self.update_progress(0, "Starting…")

        img_np = qimage_to_numpy(self.viewer.image_original).copy()
        mask_np = self.viewer.mask

        # Run model generation
        result = generate_3d_model(
            full_image_np=img_np,
            mask_np=mask_np,
            basename="myasset",
            progress_callback=self.update_progress
        )

        # Build message
        msg = (
            
            f"OBJ saved to:\n{result['obj_path']}\n\n"
        )

        if result["maya_imported_obj"]:
            msg += "Imported into Maya \n"
    
        else:
            msg += "Nothing imported into Maya.\n"

        QMessageBox.information(self, "3D Model Generated", msg)

        # Set final progress state
        self.update_progress(100, "Done!")


# endpoint
def main():
    import sys
    app = QtWidgets.QApplication(sys.argv)
    w = MainWindow()
    w.show()
    app.exec()


if __name__ == "__main__":
    main()
