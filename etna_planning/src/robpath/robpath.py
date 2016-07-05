import numpy as np

import mesh
from rapid import ABB_Robot


class RobPath():
    def __init__(self):
        self.mesh = None
<<<<<<< HEAD
        self.filled = True
=======
>>>>>>> d3ed556e67d821343be06efe0997e8100b6a1ab7
        self.rob_parser = ABB_Robot()

    def load_mesh(self, filename):
        self.mesh = mesh.Mesh(filename)
        # TODO: Change bpoints.
        self.mesh.translate(np.float32([20, 20, 0]))
        position = self.mesh.bpoint1  # Rename to position
        size = self.mesh.bpoint2 - self.mesh.bpoint1  # Change by size
        print np.vstack(self.mesh.triangles)

    def translate_mesh(self, position):
        self.mesh.translate(position)

    def resize_mesh(self, size):
        scale = size / self.mesh.size
        self.mesh.scale(scale)

    def set_power(self, power):
        self.rob_parser.power = power

    def set_speed(self, speed):
        self.rob_parser.track_speed = speed

    def set_track(self, height, width, overlap):
        self.track_height = height
        self.track_width = width
        self.track_overlap = overlap
        self.track_distance = (1 - overlap) * width
        print 'Track distance:', self.track_distance

    def set_powder(self, carrier_gas, stirrer, turntable):
        self.rob_parser.carrier_gas = carrier_gas
        self.rob_parser.stirrer = stirrer
        self.rob_parser.turntable = turntable

    def init_process(self):
        self.k = 0
        self.path = []
        self.slices = []
        self.pair = False
<<<<<<< HEAD
        self.levels = mesh.get_range_values(self.mesh.z_min,
                                            self.mesh.z_max,
                                            self.track_height)

    def update_process(self):
        slice = self.mesh.get_slice(self.levels[self.k])
        if slice is not None:
            if self.filled:
                fill_lines = self.mesh.get_grated(slice, self.track_distance)

                # Reverse the order of the slicer fill lines
                if self.pair:
                    fill_lines.reverse()
                self.pair = not self.pair

                tool_path = self.mesh.get_path_from_fill_lines(fill_lines)
            else:
                tool_path = self.mesh.get_path_from_slices([slice])
            self.slices.append(slice)
            self.path.extend(tool_path)
        self.k = self.k + 1
        print 'k, levels:', self.k, len(self.levels)

    def get_contours_path(self):
        self.k = 0
        self.path = []
        self.slices = []
        self.pair = False
        self.levels = mesh.get_range_values(self.mesh.z_min,
                                            self.mesh.z_max,
                                            self.track_height)
        slices = [self.mesh.get_slice(level) for level in self.levels]
        self.path = self.mesh.get_path_from_slices(slices)

    def save_rapid(self):
        filename = 'etna.mod'
        directory = 'ETNA'
=======
        self.levels = self.mesh.get_zlevels(self.track_height)
        self.mesh.resort_triangles()
        return self.levels

    def update_process(self, filled=True, contour=False):
        slice = self.mesh.get_slice(self.levels[self.k])
        if slice is not None:
            self.slices.append(slice)
            if filled:
                tool_path = self.mesh.get_path_from_slice(
                    slice, self.track_distance, self.pair)
                self.pair = not self.pair
                self.path.extend(tool_path)
            if contour:
                tool_path = self.mesh.get_path_from_slices([slice])
                self.path.extend(tool_path)
        self.k = self.k + 1
        print 'k, levels:', self.k, len(self.levels)
        return tool_path

    def save_rapid(self, filename='etna.mod', directory='ETNA'):
>>>>>>> d3ed556e67d821343be06efe0997e8100b6a1ab7
        routine = self.rob_parser.path2rapid(self.path)
        self.rob_parser.save_file(filename, routine)
        self.rob_parser.upload_file(filename, directory)
        print routine
<<<<<<< HEAD
=======


if __name__ == "__main__":
    import argparse
    from mlabplot import MPlot3D

    parser = argparse.ArgumentParser()
    parser.add_argument('-m', '--mesh', type=str,
                        default='../../data/piece0.stl',
                        help='path to input stl data file')
    args = parser.parse_args()

    filename = args.mesh

    robpath = RobPath()
    robpath.load_mesh(filename)
    robpath.set_track(0.5, 2.5, 0.4)
    levels = robpath.init_process()
    for k, level in enumerate(levels):
        robpath.update_process(filled=False)

    mplot3d = MPlot3D()
    #mplot3d.draw_mesh(robpath.mesh)
    #mplot3d.draw_slices(slices)
    mplot3d.draw_path(robpath.path)
    #mplot3d.draw_path_tools(_path)
    mplot3d.show()
>>>>>>> d3ed556e67d821343be06efe0997e8100b6a1ab7
