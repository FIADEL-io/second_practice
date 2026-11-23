import unittest

from depgraph.graph import GraphError, build_graph, format_graph
from depgraph.letter_graph import parse_letter_graph
from depgraph.resolve import crate_dependencies


class GraphTests(unittest.TestCase):

    def test_bfs_order_is_level_by_level(self) -> None:
        described = {"A": ("B", "C"), "B": ("D",), "C": ("D",), "D": ()}
        graph = build_graph("A", lambda node: list(described[node]), "")
        self.assertEqual(graph.order, ("A", "B", "C", "D"))
        self.assertEqual(graph.adjacency["A"], ("B", "C"))
        self.assertEqual(graph.cycles, ())

    def test_recursion_does_not_loop_on_cycle(self) -> None:
        described = {"A": ("B",), "B": ("A",)}
        graph = build_graph("A", lambda node: list(described[node]), "")
        self.assertEqual(graph.order, ("A", "B"))
        self.assertEqual(graph.cycles, (("A", "B", "A"),))

    def test_self_loop_is_a_cycle(self) -> None:
        graph = build_graph("A", lambda _node: ["A"], "")
        text = format_graph(graph)
        self.assertIn("цикл: A -> A", text)

    def test_filter_drops_matching_names(self) -> None:
        described = {"A": ("B", "C"), "B": ("D",), "C": ("D",), "D": ()}
        graph = build_graph("A", lambda node: list(described[node]), "C")
        self.assertNotIn("C", graph.order)
        self.assertEqual(graph.adjacency["A"], ("B",))
        self.assertIn("D", graph.order)

    def test_root_filter_is_an_error(self) -> None:
        with self.assertRaises(GraphError):
            build_graph("ABC", lambda _node: [], "B")

    def test_letter_graph_rejects_lowercase(self) -> None:
        with self.assertRaises(GraphError):
            parse_letter_graph("A: b\n")

    def test_crate_dependencies_keep_normal_only(self) -> None:
        pages = {
            "https://crates.io/api/v1/crates/demo": (
                '{"crate": {"max_stable_version": "1.2.0"}}'
            ),
            "https://crates.io/api/v1/crates/demo/1.2.0/dependencies": (
                '{"dependencies": ['
                '{"crate_id": "left", "req": "^1", "kind": "normal"},'
                '{"crate_id": "temp", "req": "3", "kind": "dev"}'
                "]}"
            ),
        }

        def fetch(url: str) -> str:
            text = pages.get(url)
            if text is None:
                raise AssertionError(url)
            return text

        found = crate_dependencies("demo", "", fetch)
        self.assertEqual(found, [("left", "^1")])


if __name__ == "__main__":
    unittest.main()
