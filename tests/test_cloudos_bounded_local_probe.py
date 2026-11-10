import unittest
from scripts.perf.cloudos_bounded_local_probe import nearest_rank, validate_args


class BoundedLocalProbeTests(unittest.TestCase):
    def test_rejects_burst_and_invalid_paths(self):
        for n, w, p in [(1001, 1, "/up"), (20, 20, "/up"), (2, 1, "/login"), (2, True, "/up"), (0, 1, "/")]:
            with self.subTest(values=(n, w, p)), self.assertRaises(ValueError):
                validate_args(n, w, p)

    def test_nearest_rank_latency(self):
        self.assertEqual(nearest_rank([20, 5, 15, 10], .95), 20)
        self.assertEqual(nearest_rank([20, 5, 15, 10], .50), 10)
        self.assertEqual(nearest_rank([], .99), 0)

    def test_safe_small_plan(self):
        validate_args(50, 4, "/up")


if __name__ == "__main__":
    unittest.main()
