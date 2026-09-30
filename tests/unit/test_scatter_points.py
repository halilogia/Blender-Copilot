import math
import unittest

from core.scatter_points import (area_bounds, height_at, height_grid, min_distance_for, rect_of_box, sample_area, sample_path,
                                 value_noise)

AREA = {"center": [0, 0], "size": [20, 20]}


class SamplingTests(unittest.TestCase):
    def test_area_points_are_inside_spaced_and_seeded(self):
        pts = sample_area(AREA, 30, 2.0, seed=4)
        self.assertEqual(len(pts), 30)
        self.assertTrue(all(-10 <= x <= 10 and -10 <= y <= 10 for x, y in pts))
        self.assertTrue(all(math.dist(a, b) >= 2.0 - 1e-9 for i, a in enumerate(pts) for b in pts[i + 1:]))
        self.assertEqual(pts, sample_area(AREA, 30, 2.0, seed=4))
        self.assertNotEqual(pts, sample_area(AREA, 30, 2.0, seed=5))

    def test_circle_and_crowding(self):
        pts = sample_area({"center": [5, 5], "radius": 3}, 20, 0.5, seed=1)
        self.assertTrue(all(math.dist(p, (5, 5)) <= 3 + 1e-9 for p in pts))
        crowded = sample_area({"center": [0, 0], "size": [2, 2]}, 50, 1.5, seed=1)
        self.assertLess(len(crowded), 50)            # asks for more than fits: returns what fits, not an error

    def test_avoid_boxes_are_kept_clear(self):
        pts = sample_area(AREA, 40, 1.0, seed=2, avoid=[(-3, -3, 3, 3)])
        self.assertTrue(pts and all(not (-3 <= x <= 3 and -3 <= y <= 3) for x, y in pts))

    def test_path_points_stay_near_the_line(self):
        pts = sample_path([[0, 0], [20, 0]], 25, spread=1.5, min_distance=0.5, seed=3)
        self.assertGreater(len(pts), 15)
        self.assertTrue(all(-0.1 <= x <= 20.1 and abs(y) <= 1.5 + 1e-9 for x, y in pts))
        bent = sample_path([[0, 0], [10, 0], [10, 10]], 30, spread=0.0, min_distance=0.2, seed=3)
        self.assertTrue(all(abs(y) < 1e-9 or abs(x - 10) < 1e-9 for x, y in bent))

    def test_bad_inputs_name_the_problem(self):
        for bad in ("x", {"size": [0, 5]}, {"center": [0, 0]}, {"radius": -1}):
            with self.assertRaises(ValueError):
                area_bounds(bad)
        for bad_path in ([[0, 0]], [[1, 1], [1, 1]], "abc", [[0, "a"], [1, 1]]):
            with self.assertRaises(ValueError):
                sample_path(bad_path, 5, 1.0, 0.5, 1)

    def test_helpers(self):
        self.assertEqual(rect_of_box((0, 0, 0), (2, 4, 1), 1.0), (-1.0, -1.0, 3.0, 5.0))
        self.assertAlmostEqual(min_distance_for(2, 3, 1.5, None), 3 * 1.5 * 0.9)
        self.assertEqual(min_distance_for(2, 3, 1.5, 0.7), 0.7)


class TerrainTests(unittest.TestCase):
    def test_noise_is_smooth_bounded_and_seeded(self):
        values = [value_noise(i * 0.37, i * 0.11, 7) for i in range(200)]
        self.assertTrue(all(0.0 <= v <= 1.0 for v in values))
        self.assertEqual(value_noise(1.3, 2.1, 7), value_noise(1.3, 2.1, 7))
        self.assertNotEqual(value_noise(1.3, 2.1, 7), value_noise(1.3, 2.1, 8))
        self.assertLess(abs(value_noise(1.0, 1.0, 3) - value_noise(1.001, 1.0, 3)), 0.01)

    def test_height_grid_shape_range_and_flat_centre(self):
        grid = height_grid(40.0, 20, 5.0, 0.5, seed=2, flat_radius=6.0)
        self.assertEqual((len(grid), len(grid[0])), (21, 21))
        flat = [v for row in grid for v in row]
        self.assertTrue(0.0 <= min(flat) and max(flat) <= 5.0 + 1e-9)
        self.assertGreater(max(flat) - min(flat), 1.0)
        self.assertEqual(grid[10][10], 0.0)           # the centre is flat
        self.assertEqual(height_at(0.5, 0.5, 40.0, 5.0, 0.5, 2, 6.0), 0.0)
        self.assertEqual(grid, height_grid(40.0, 20, 5.0, 0.5, seed=2, flat_radius=6.0))
        rougher = height_grid(40.0, 20, 5.0, 0.9, seed=2)
        smoother = height_grid(40.0, 20, 5.0, 0.1, seed=2)
        step = lambda g: sum(abs(g[j][i + 1] - g[j][i]) for j in range(21) for i in range(20))
        self.assertGreater(step(rougher), step(smoother))


if __name__ == "__main__":
    unittest.main()
