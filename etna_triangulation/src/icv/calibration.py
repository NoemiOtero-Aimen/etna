import cv2
import yaml
import numpy as np
import numpy.linalg as la

from image import *
from drawing import *
import fitting as fit
import calculate as calc

from profile import Profile
from mlabplot import MPlot3D


# ----------------------------------------------------------------------------

class CameraCalibration():
    def __init__(self, grid_size=(7,6), square_size=10.0):
        self.grid_size = grid_size
        self.square_size = square_size
        self.targets = self.get_pattern_points()
        self.pattern_points = np.float32([[point[0], point[1], 0] for point in self.targets])

    def get_pattern_points(self):
        points = np.zeros((np.prod(self.grid_size), 2), np.float32)
        points[:,:2] = np.indices(self.grid_size).T.reshape(-1, 2)
        points *= self.square_size
        #points += self.grid_orig
        return points

    def load_camera_parameters(self, filename):
        with open(filename, 'r') as f:
            data = yaml.load(f)
        self.rms = data['rms']
        self.camera_mat = np.array(data['mat'])
        self.dist_coef = np.array(data['coef'])
        return data

    def save_camera_parameters(self, filename):
        data = dict(rms = self.rms,
                    mat = self.camera_mat.tolist(),
                    coef = self.dist_coef.tolist())
        with open(filename, 'w') as f:
            f.write(yaml.dump(data))
        return data

    def find_chessboard(self, img):
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        grid = None
        found, corners = cv2.findChessboardCorners(gray, self.grid_size)
        if found:
            term = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_COUNT, 30, 0.1) # termination criteria
            cv2.cornerSubPix(gray, corners, (5, 5), (-1, -1), term)
            grid = corners.reshape((self.grid_size[0], self.grid_size[1], 2))
        return grid

    def get_chessboard_pose(self, grid):
        """Gets the estimated pose for the calibration chessboard."""
        if grid is None:
            return None
        else:
            corners = grid.reshape((-1, 2))
            return self.find_transformation(self.pattern_points, corners)

    def read_filenames(self, filenames):
        return sorted(glob.glob(filenames))

    def read_images(self, filenames):
        images = [read_image(filename) for filename in filenames]
        return images

    def find_patterns(self, images):
        patterns = [self.find_chessboard(img) for img in images]
        return patterns

    def locate_patterns(self, grids):
        poses = [self.get_chessboard_pose(grid) for grid in grids]
        return poses

    def get_calibration(self, images):
        """Gets the camera parameters solving the calibration problem."""
        # Arrays to store object points and image points from all the images.
        obj_points = [] # 3d point in real world space
        img_points = [] # 2d points in image plane.
        self.grids = self.find_patterns(images)
        for grid in self.grids:
            if grid is not None:
                corners = grid.reshape((-1, 2))
                img_points.append(corners)
                obj_points.append(self.pattern_points)
        self.rms, self.camera_mat, self.dist_coef, rvecs, tvecs = cv2.calibrateCamera(obj_points, img_points, get_size(images[0]))
        self.calculate_reprojection_errors(self.grids)
        return self.camera_mat, self.dist_coef

    def find_transformation(self, object_points, image_points):
        """Finds the rotation and translation transformation."""
        rvecs, tvecs, inliers = cv2.solvePnPRansac(object_points, image_points,
                                                   self.camera_mat, self.dist_coef)
        R, t = cv2.Rodrigues(rvecs)[0], tvecs.reshape(-1)
        return R, t

    def project_3d_points(self, points, pose):
        """Projects 3D points to image coordinates."""
        R, t = pose
        rvecs, tvecs = cv2.Rodrigues(R)[0], np.float32([t]).T
        imgpts, jac = cv2.projectPoints(points, rvecs, tvecs, self.camera_mat, self.dist_coef)
        return imgpts.reshape((-1, 2))

    def reprojection_error(self, points3d, imgpoints, pose):
        """Calculates the re-projection error, how exact is the estimation of
        the found parameters. This should be as close to zero as possible.
        Given the intrinsic, distortion, rotation and translation matrices,
        we first transform the object point to image point using
        cv2.projectPoints(). Then we calculate the absolute norm between the
        image points. To find the average error we calculate the arithmetical
        mean of the errors calculated."""
        #tot_error = 0
        #mean_error = 0
        imgpoints2 = self.project_3d_points(points3d, pose)
        error = cv2.norm(imgpoints, imgpoints2, cv2.NORM_L2) / len(imgpoints2)
        return error

    def chessboard_reprojection_error(self, grid):
        """Gets the reprojection error for the calibration chessboard."""
        corners = grid.reshape((-1, 2))
        points3d = self.pattern_points
        chessboard_pose = self.get_chessboard_pose(grid)
        return self.reprojection_error(points3d, corners, chessboard_pose)

    # TODO: Add rejected criterium, and data structure with data for each image
    def calculate_reprojection_errors(self, grids):
        for grid in grids:
            if grid is not None:
                print 'Error', self.chessboard_reprojection_error(grid)

    def undistort_image(self, image):
        display = cv2.undistort(image.copy(), self.camera_mat, self.dist_coef)
        return display

    def undistort_points(self, points):
        points = cv2.undistortPoints(np.float32([points]), self.camera_mat,
                                     self.dist_coef).reshape((-1, 2))
        fx, fy = self.camera_matrix[0,0], self.camera_matrix[1,1]
        cx, cy = self.camera_matrix[0,2], self.camera_matrix[1,2]
        # Normalized coordinated are transformed to image coordinates.
        points = points * np.float32([fx, fy]) + np.float32([cx, cy])
        return points

    def draw_chessboard(self, image, corners):
        if corners is not None:
            rows, cols = corners.shape[:2]
            corners = corners.reshape((-1, 2))
            cv2.drawChessboardCorners(image, (rows, cols), corners, True)
        return image

    def draw_frame(self, img, pose, size=(30, 30, 30)):
        sx, sy, sz = size
        corners = np.float32([[0, 0, 0], [sx, 0, 0], [0, sy,0], [0, 0, sz]])
        imgpts = self.project_3d_points(corners, pose)
        cv2.line(img, tuple(imgpts[0]), tuple(imgpts[1]), (0, 0, 255), 5)
        cv2.line(img, tuple(imgpts[0]), tuple(imgpts[2]), (0, 255, 0), 5)
        cv2.line(img, tuple(imgpts[0]), tuple(imgpts[3]), (255, 0, 0), 5)
        return img

    def draw_box(self, img, pose, size=(30, 30, 30), thickness=3):
        axis = np.float32([[0, 0, 0], [0, 1, 0], [1, 1, 0], [1, 0, 0],
                           [0, 0, -1], [0, 1, -1], [1, 1, -1], [1, 0, -1]]) * np.float32(size)
        imgpts = np.int32(self.project_3d_points(axis, pose))
        cv2.drawContours(img, [imgpts[:4]], -1, (0, 255, 0), thickness)
        for i, j in zip(range(4),range(4,8)):
            cv2.line(img, tuple(imgpts[i]), tuple(imgpts[j]), (255, 0, 0), thickness)
        cv2.drawContours(img, [imgpts[4:]],-1, (0, 0, 255), thickness)
        return img


# ----------------------------------------------------------------------------

class LaserCalibration(CameraCalibration):
    def __init__(self, grid_size=(7,6), square_size=10.0, profile=Profile()):
        CameraCalibration.__init__(self, grid_size=grid_size, square_size=square_size)
        self.camera_pose = (np.eye(3), np.zeros(3))
        self.profile = profile

    def load_parameters(self, filename):
        return self.profile.load_configuration(filename)

    def save_parameters(self, filename):
        return self.profile.save_configuration(filename)

    def get_camera_pose(self, global_points, image_points):
        camera_pose = self.find_transformation(global_points, image_points)
        return camera_pose

    def find_best_line2d(self, points2d):
        line = fit.LineFit()
        model, inliers = line.ransac(points2d, line, int(0.5*len(points2d)), 5)
        return model, inliers

    def find_best_plane(self, points3d):
        plane = fit.PlaneFit()
        model, inliers = plane.ransac(points3d, plane, int(0.5*len(points3d)), 20)
        return model, inliers

    def find_plane_transformation(self, plane_pose):
        """Finds the homography transformation for a plane pose."""
        camera_pose = (np.eye(3), np.zeros(3))
        points3d = calc.transform_points2d(self.targets, plane_pose)
        points2d = self.project_3d_points(points3d, camera_pose)
        homography = find_homography(points2d, self.targets)
        return homography

    def find_lightplane(self, points3d):
        """Calculates the transformation between the image points and the lightplane."""
        plane, inliers = self.find_best_plane(points3d)
        plane_pose = fit.get_plane_pose(plane)
        plane_homography = self.find_plane_transformation(plane_pose)
        return plane_pose, plane_homography

    def filter_chessboard_laser(self, profile3d, profile2d):
        """Filter points by reprojection error."""
        vpoints2d, vpoints3d = [], []
        for k in range(len(profile2d)):
            error = self.reprojection_error(np.float32([profile3d[k]]),
                                                np.float32([profile2d[k]]),
                                                self.camera_pose)
            if error < 1:
                vpoints2d.append(profile2d[k])
                vpoints3d.append(profile3d[k])
        profile2d = np.float32(vpoints2d)
        profile3d = np.float32(vpoints3d)
        return profile3d, profile2d

    def get_chessboard_laser(self, img, grid):
        chessboard_pose = self.get_chessboard_pose(grid)
        homography = find_homography(grid.reshape((-1, 2)), self.targets)
        profile3d, profile2d = self.profile.points_profile(img, homography, chessboard_pose)
        profile3d, profile2d = self.filter_chessboard_laser(profile3d, profile2d)
        return profile3d, profile2d, chessboard_pose

    def find_profiles(self, images):
        profiles = [self.profile.profile_points(img) for img in images]
        return profiles

    def find_homographies(self, grids):
        homographies = []
        for grid in grids:
            corners = grid.reshape((-1, 2))
            homography = find_homography(corners, self.targets)
            homographies.append(homography)
        return homographies

    def find_lines(self, profiles):
        # line, inliers
        lines = [self.find_best_line2d(profile2d) for profile2d in profiles]
        return lines

    def find_calibration_3d(self, filenames):
        filenames = self.read_filenames(filenames)
        images = self.read_images(filenames)
        self.get_calibration(images)
        self.images = images

        profiles3d = []
        for k, img in enumerate(images):
            grid = self.grids[k]
            if grid is not None:
                profile3d, profile2d, chessboard_pose = self.get_chessboard_laser(img, grid)
                if len(profile2d) > 0:
                    line, inliers = self.find_best_line2d(profile2d)
                    profiles3d.append(profile3d[inliers])
        self.profiles3d = np.vstack(profiles3d)

        self.profile.pose, self.profile.homography = self.find_lightplane(self.profiles3d)

    def show_calibration_3d(self, images):
        print 'Camera calibration'
        print self.camera_mat, self.dist_coef

        print 'Laser pose and transformation'
        print self.profile.pose, self.profile.homography

        mplot3d = MPlot3D(scale=0.005)
        for k, img in enumerate(images):
            grid = self.grids[k]
            if grid is not None:
                profile3d, profile2d, chessboard_pose = self.get_chessboard_laser(img, grid)
                if len(profile2d) > 0:
                    mplot3d.draw_frame(chessboard_pose)
                    mplot3d.draw_points(profile3d, color=(1, 1, 1))

        plane, inliers = self.find_best_plane(self.profiles3d)
        mplot3d.draw_plane(plane, self.profiles3d[inliers])

        mplot3d.draw_points(self.profiles3d, color=(1, 1, 0))
        mplot3d.draw_points(self.profiles3d[inliers], color=(0,0,1))
        # Draws camera and laser poses
        mplot3d.draw_frame(self.profile.pose, label='laser')
        points3d = calc.transform_points2d(self.targets, self.camera_pose)
        mplot3d.draw_camera(self.camera_pose, color=(0.8, 0.8, 0.8))
        mplot3d.draw_points(points3d, color=(1, 1, 1))
        mplot3d.show()

    def draw_location_results(self, img, frame_rate):
        text = ''
        gray = self.profile.threshold_image(img)
        grid = self.find_chessboard(img)
        if grid is not None:
            img = draw_chessboard(img, grid)
        text += 'FPS: %.1f\n' %(frame_rate)
        profile_points = self.profile.peak_profile(gray)
        img = draw_points(img, profile_points, color=RED, thickness=2)
        img = draw_text(img, (10, 20), text)
        return img


# ----------------------------------------------------------------------------

class HandEyeCalibration():
    """Class for hand eye calibration.

    It implements the TsaiLenz method.

    References: R.Tsai, R.K.Lenz "A new Technique for Fully Autonomous
            and Efficient 3D Robotics Hand/Eye calibration", IEEE
            trans. on robotics and Automaion, Vol.5, No.3, June 1989
    """

    def __init__(self):
        pass

    def _skew(self, v):
        if len(v) == 4: v = v[:3]/v[3]
        skv = np.roll(np.roll(np.diag(v.flatten()), 1, 1), -1, 0)
        return skv - skv.T

    def _quat_to_rot(self, q):
        """
        Converts a unit quaternion (3x1) to a rotation matrix (3x3).
        %
        %    R = quat2rot(q)
        %
        %    q - 3x1 unit quaternion
        %    R - 4x4 homogeneous rotation matrix (translation component is zero)
        %        q = sin(theta/2) * v
        %        teta - rotation angle
        %        v    - unit rotation axis, |v| = 1
        %
        """
        q = np.array(q).reshape(3,1)
        p = np.dot(q.T,q).reshape(1)[0]
        if p > 1:
            print('Warning: quaternion greater than 1')
        w = np.sqrt(1 - p)
        R = np.eye(4)
        R[:3,:3] = 2*q*q.T + 2*w*self._skew(q) + np.eye(3) - 2*np.diag([p,p,p])
        return R

    def _rot_to_quat(self, R):
        """
        Converts a rotation matrix (3x3) to a unit quaternion (3x1).
        %
        %    q = rot2quat(R)
        %
        %    R - 3x3 rotation matrix, or 4x4 homogeneous matrix
        %    q - 3x1 unit quaternion
        %        q = sin(theta/2) * v
        %        teta - rotation angle
        %        v    - unit rotation axis, |v| = 1
        %
        """
        w4 = 2 * np.sqrt(1 + np.trace(R[:3,:3]))
        q = np.array([(R[2,1] - R[1,2]) / w4,
                      (R[0,2] - R[2,0]) / w4,
                      (R[1,0] - R[0,1]) / w4])
        return q

    def solve(self, Hgs, Hcs): # list of poses

        # // Calculate rotational component
        M = len(Hgs)
        lhs = []
        rhs = []
        for i in range(M):
            for j in range(i+1,M):
                Hgij = np.dot(la.inv(Hgs[j]), Hgs[i])
                Pgij = 2 * self._rot_to_quat(Hgij)
                Hcij = np.dot(Hcs[j], la.inv(Hcs[i]))
                Pcij = 2 * self._rot_to_quat(Hcij)
                lhs.append(self._skew(Pgij + Pcij))
                rhs.append(Pcij - Pgij)
        lhs = np.array(lhs)
        lhs = lhs.reshape(lhs.shape[0]*3, 3)
        rhs = np.array(rhs)
        rhs = rhs.reshape(rhs.shape[0]*3)
        Pcg_, res, rank, sing = np.linalg.lstsq(lhs, rhs)
        Pcg = 2 * Pcg_ / np.sqrt(1 + np.dot(Pcg_, Pcg_))
        #Rcg = (1 - 0.5 * np.dot(Pcg, Pcg)) * np.eye(3) + 0.5 * (np.dot(Pcg.reshape(3,1), Pcg.reshape(1,3)) + np.sqrt(4 - np.dot(Pcg, Pcg)) * self._skew(Pcg))
        Rcg = self._quat_to_rot(Pcg / 2)

        # // Calculate translational component
        lhs = []
        rhs = []
        for i in range(M):
            for j in range(i+1,M):
                Hgij = np.dot(la.inv(Hgs[j]), Hgs[i])
                Hcij = np.dot(Hcs[j], la.inv(Hcs[i]))
                lhs.append(Hgij[:3,:3] - np.eye(3))
                rhs.append(np.dot(Rcg[:3,:3], Hcij[:3,3]) - Hgij[:3,3])
        lhs = np.array(lhs)
        lhs = lhs.reshape(lhs.shape[0]*3, 3)
        rhs = np.array(rhs)
        rhs = rhs.reshape(rhs.shape[0]*3)
        Tcg, res, rank, sing = np.linalg.lstsq(lhs, rhs)

        Hcg = np.eye(4)
        Hcg[:3,:3] = Rcg[:3,:3]
        Hcg[:3,3] = Tcg
        return Hcg



if __name__ == '__main__':
    np.set_printoptions(precision=4, suppress=True)

    import os
    import glob

    dirname = '../data/rdata'
    filenames = os.path.join(dirname, 'frame*.png')
    laser_profile = Profile(axis=1, thr=180, method='pcog')
    laser_calibration = LaserCalibration(grid_size=(7,6), square_size=0.010, profile=laser_profile)
    laser_calibration.find_calibration_3d(filenames)

    images = laser_calibration.images
    grids = laser_calibration.grids
    poses = laser_calibration.locate_patterns(grids)
    profiles = laser_calibration.find_profiles(images)
    #homographies = laser_calibration.find_homographies(grids)
    lines = laser_calibration.find_lines(profiles)

    for k, img in enumerate(images):
        #imgc = img.copy()
        imgc = laser_calibration.draw_chessboard(img.copy(), grids[k])
        #cv2.imwrite('board%i.png' %k, imgc)
        if len(profiles[k]) > 0:
            line, inliers = lines[k]
            imgc = draw_points(imgc, profiles[k], color=PURPLE, thickness=2)
            line = ((0, int(line[0] * 0 + line[1])),
                    (int(img.shape[1]), int(line[0] * img.shape[1] + line[1])))
            imgc = draw_points(imgc, profiles[k][inliers], color=RED, thickness=2)
            imgc = draw_line(imgc, line, color=RED, thickness=2)
            #cv2.imwrite('board%i.png' %k, imgc)
        show_images([imgc], wait=500)

    #laser_calibration.show_calibration_3d(images)
    #laser_calibration.save_parameters('../config/triangulation.yml')

    filenames = sorted(glob.glob(os.path.join(dirname, 'pose*.txt')))
    ks = [int(filename[-8:-4]) for filename in filenames]
    poses_checker, poses_tool = [], []
    for k in ks:
        img = read_image(os.path.join(dirname, 'frame%04i.png' %k))
        grid = laser_calibration.find_chessboard(img)
        pose_checker = None
        pose_tool0 = None
        if grid is not None:
            pose_checker = laser_calibration.get_chessboard_pose(grid)
            pose_checker = calc.pose_to_matrix(pose_checker)
            with open(os.path.join(dirname, 'pose%04i.txt' %k), 'r') as f:
                pose = eval(f.read())
                quatpose_tool0 = (np.array(pose[0]), np.array(pose[1]))
                pose_tool0 = calc.quatpose_to_matrix(*quatpose_tool0)
        poses_checker.append(pose_checker)
        poses_tool.append(pose_tool0)
    #RZ180 = calc.rpypose_to_matrix((0.06,0.05,0), (0, 0, np.pi))
    #poses_checker = [calc.matrix_compose((pose_checker, RZ180)) for pose_checker in poses_checker]
    print 'Poses:', poses_checker, poses_tool
    pchecker, ptool = [], []
    for k in range(len(poses_checker)):
        if poses_checker[k] is not None:
            pchecker.append(poses_checker[k])
            ptool.append(poses_tool[k])
    poses_checker, poses_tool = pchecker, ptool
    poses_ichecker = [calc.matrix_invert(pose_checker) for pose_checker in poses_checker]
    poses_itool = [calc.matrix_invert(pose_tool) for pose_tool in poses_tool]

    print 'Hand Eye Calibration Solution'
    tlc = HandEyeCalibration()
    T2C = tlc.solve(poses_tool, poses_checker)
    W2K = tlc.solve(poses_itool, poses_ichecker)
#    Htc = tlc.solve([WT1, WT2, WT3], [CK1, CK2, CK3])
#    Hwk = tlc.solve([TW1, TW2, TW3], [KC1, KC2, KC3])
#    T2C, W2K = Htc, Hwk
    print 'Tool2Camera:', calc.matrix_to_rpypose(T2C)
    print 'World2Checker:', calc.matrix_to_rpypose(W2K)

    #T2C = calc.matrix_compose((T2C, RZ180))
    #print 'Tool2Camera (rot):', calc.matrix_to_rpypose(T2C)

    mplot3d = MPlot3D(scale=0.005)
    world_frame = calc.rpypose_to_matrix([0, 0, 0], [0, 0, 0])
    mplot3d.draw_frame(calc.matrix_to_pose(world_frame), label='world_frame')
    for k, tool_frame in enumerate(poses_tool):
        WC = calc.matrix_compose((tool_frame, T2C))
        mplot3d.draw_transformation(world_frame, tool_frame)
        mplot3d.draw_transformation(tool_frame, WC, 'tool_pose%i'%k, 'camera_pose%i'%k)
        WK = calc.matrix_compose((WC, poses_checker[k]))
        print 'Checker %i ->' %k, WK
        print np.allclose(W2K, WK, atol=0.00001)
        mplot3d.draw_frame(calc.matrix_to_pose(WK))
        mplot3d.draw_points(calc.points_transformation(WK, laser_calibration.pattern_points), color=(1,1,0))

        mplot3d.draw_frame(calc.matrix_to_pose(W2K))
        mplot3d.draw_points(calc.points_transformation(W2K, laser_calibration.pattern_points), color=(1,1,1))

        img, grid = images[k], laser_calibration.grids[k]
        if grid is not None:
            profile3d, profile2d, chessboard_pose = laser_calibration.get_chessboard_laser(img, grid)
            chessboard_pose = calc.matrix_compose((WC, calc.pose_to_matrix(chessboard_pose)))
            if len(profile2d) > 0:
                mplot3d.draw_points(calc.points_transformation(WC, profile3d), color=(1, 1, 1))

    mplot3d.show()

#    # TODO: Add hand eye calibration: automatic calibration
#    # TODO: Change calibration units to meters. (remove millimeters)
#    # TODO: Standardize transformation functions: halcon inspired.
#    # TODO: Remove pose (R,t). Replace with homogeneous transformation matrices.
#    # TODO: Integrate rviz with workcell calibration tools.
#    # TODO: Modified RAPID script: power, powder, triggers. Check TCP sign.
