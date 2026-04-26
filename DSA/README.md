# Data Structures & Algorithms

Personal coding practice with Jupyter notebooks - questions, test cases, and detailed solutions.

## Quick Start

```bash
cd DSA
make vm-start && make start
```

Access at: **http://localhost:8888/lab** (no token required)

See [podman.md](podman.md) for container setup and commands.

## Structure

```

├── linear/
│   ├── arrays_and_string/
│   │   ├── concepts.ipynb
│   │   ├── arrays_and_strings_questions.ipynb
│   │   └── arrays_and_strings_solutions.ipynb
│   ├── linked_list/
│   └── stacks_queues/
│
├── nonlinear/
│   ├── trees/
│   ├── graphs/
│   ├── heaps/
│   ├── tries/
│   └── backtracking/
│
├── search/
│   ├── concepts.ipynb
│   ├── binary_search_questions.ipynb
│   └── binary_search_solutions.ipynb
│
└── notebooks/
```

Each topic contains:
- `concepts.ipynb` - Theory and patterns
- `*_questions.ipynb` - Practice problems with test cases
- `*_solutions.ipynb` - Solutions with explanations

## How to Practice

1. Start with the **concepts** notebook for theory
2. Open the **questions** notebook
3. Read the problem and implement your solution
4. Run the test cases to verify
5. Check the **solutions** notebook if stuck

## Topics Covered

### Linear
- **Arrays & Strings:** Two pointers, sliding window, hash maps, prefix sum
- **Linked Lists:** Reversal, cycle detection, merge, fast/slow pointers
- **Stacks & Queues:** Monotonic stack, valid parentheses, BFS patterns

### Non-Linear
- **Trees:** DFS/BFS traversals, BST operations, LCA, serialization
- **Graphs:** Grid traversal, cycle detection, topological sort, connected components
- **Heaps:** Priority queues, top-K problems, merge K sorted lists
- **Tries:** Prefix matching, autocomplete, word search
- **Backtracking:** Subsets, permutations, combinations, N-Queens

### Search
- **Binary Search:** Search space reduction, rotated arrays, finding boundaries
