"""
Production-Ready Tic-Tac-Toe AI
Optimal via alpha-beta minimax with memoization (never loses)
"""

from functools import lru_cache

rectangle_mapping = {
    (0, 0): 1, (0, 1): 2, (0, 2): 3,
    (1, 0): 4, (1, 1): 5, (1, 2): 6,
    (2, 0): 7, (2, 1): 8, (2, 2): 9,
}

# All possible winning lines (as index triplets in flattened board)
LINE_IDXS = [
    (0,1,2), (3,4,5), (6,7,8),  # rows
    (0,3,6), (1,4,7), (2,5,8),  # cols
    (0,4,8), (2,4,6)            # diagonals
]

def _flat(board):
    """Flatten 3x3 list board -> tuple of 9 cells."""
    return tuple(board[r][c] for r in range(3) for c in range(3))

def _unflat_idx(i):
    return divmod(i, 3)  # -> (row, col)

def _empty_idxs(state):
    return [i for i, v in enumerate(state) if v == '']

def _winner(state):
    """Return 'X' or 'O' if someone won, else None."""
    for a,b,c in LINE_IDXS:
        v = state[a]
        if v != '' and v == state[b] == state[c]:
            return v
    return None


class InvalidBoardError(Exception):
    """Raised when board state is invalid"""
    pass


class TicTacToeAI:
    """Optimal Tic-Tac-Toe AI using alpha-beta minimax"""
    def __init__(self, ai_symbol='O', human_symbol='X'):
        if ai_symbol == human_symbol:
            raise ValueError("AI and human symbols must be different")
        self.ai = ai_symbol
        self.human = human_symbol

    def get_best_move(self, board):
        """
        Returns optimal move (row, col).
        Raises InvalidBoardError if board invalid; ValueError if no moves.
        """
        self._validate_board(board)
        state = _flat(board)

        # Quick outs: win now or block now (fast path)
        for sym in (self.ai, self.human):
            for i in _empty_idxs(state):
                s2 = list(state); s2[i] = sym; s2 = tuple(s2)
                if _winner(s2) == sym:
                    return _unflat_idx(i)

        # Minimax with alpha-beta and memoization
        best_score, best_idx = self._solve(state, self.ai, 0, -100, 100)
        if best_idx is None:
            raise ValueError("No valid moves available")
        return _unflat_idx(best_idx)

    def _validate_board(self, board):
        """Validate board shape, symbols, counts, and not already won."""
        if not (isinstance(board, list) and len(board) == 3 and all(isinstance(r, list) and len(r) == 3 for r in board)):
            raise InvalidBoardError("Board must be a 3x3 list")

        allowed = {'', self.ai, self.human}
        for r in board:
            for cell in r:
                if cell not in allowed:
                    raise InvalidBoardError(f"Invalid symbol: {cell!r}")

        state = _flat(board)
        ai_count = sum(1 for v in state if v == self.ai)
        human_count = sum(1 for v in state if v == self.human)

        # Basic count sanity (allow both orders; don't overconstrain)
        if abs(ai_count - human_count) > 1:
            raise InvalidBoardError("Invalid move counts")

        # Can't continue from an already won position
        win = _winner(state)
        if win is not None:
            raise InvalidBoardError("Game already won")

    # --- Minimax core -----------------------------------------------------

    @lru_cache(maxsize=None)
    def _solve(self, state, to_move, depth, alpha, beta):
        """
        Return (score, best_index) from this state with 'to_move' to play.
        Scores: AI win = 10 - depth, Human win = depth - 10, Draw = 0.
        """
        win = _winner(state)
        if win == self.ai:
            return (10 - depth, None)
        if win == self.human:
            return (depth - 10, None)

        empties = _empty_idxs(state)
        if not empties:
            return (0, None)

        # Move ordering: center, corners, edges (greatly speeds search)
        ordered = self._order_moves(empties)

        is_max = (to_move == self.ai)
        best_score = -100 if is_max else 100
        best_idx = None
        next_player = self.human if is_max else self.ai

        for i in ordered:
            lst = list(state); lst[i] = to_move; nxt = tuple(lst)
            score, _ = self._solve(nxt, next_player, depth + 1, alpha, beta)

            if is_max:
                if score > best_score:
                    best_score, best_idx = score, i
                alpha = max(alpha, best_score)
                if alpha >= beta:
                    break
            else:
                if score < best_score:
                    best_score, best_idx = score, i
                beta = min(beta, best_score)
                if alpha >= beta:
                    break

        return best_score, best_idx

    @staticmethod
    def _order_moves(idxs):
        """Center -> corners -> edges."""
        center = [4] if 4 in idxs else []
        corners = [i for i in (0,2,6,8) if i in idxs]
        edges = [i for i in (1,3,5,7) if i in idxs]
        return center + corners + edges


def run_algorithm(ai=None, board=None):
    """
    Run Tic-Tac-Toe AI algorithm

    Args:
        ai: TicTacToeAI instance (creates default if None)
        board: 3x3 board state

    Returns:
        Grid cell number (1-9)

    Raises:
        InvalidBoardError: If board is invalid
        ValueError: If no moves available
    """
    if board is None:
        raise ValueError("Board cannot be None")

    if ai is None:
        ai = TicTacToeAI(ai_symbol='O', human_symbol='X')

    r, c = ai.get_best_move(board)
    return rectangle_mapping[(r, c)]


# ============= TESTS =============
if __name__ == "__main__":
    def test_case(name, board, expected, description=""):
        try:
            result = run_algorithm(board=board)
            ok = (isinstance(expected, list) and result in expected) or (result == expected)
            status = "✓" if ok else "✗"
            print(f"{status} {name}: {result} (expect {expected}) {description}")
        except Exception as e:
            print(f"✗ {name}: ERROR - {e}")

    print("="*60)
    print("BASIC STRATEGY TESTS")
    print("="*60)

    test_case("Win immediately",
              [['O', 'O', ''], ['X', 'X', ''], ['', '', '']],
              3, "- Take winning move")

    test_case("Block opponent",
              [['X', 'X', ''], ['O', 'O', ''], ['', '', '']],
              [3, 6], "- Block or win")

    test_case("Block diagonal",
              [['X', 'O', ''], ['', 'X', ''], ['', '', '']],
              9, "- Block diagonal threat")

    test_case("Take center",
              [['', '', ''], ['', '', ''], ['', '', '']],
              5, "- Empty board takes center")

    test_case("Edge case",
              [['', '', 'X'], ['X', 'O', 'O'], ['', '', 'X']],
              [1, 2, 3, 7, 8], "- Strategic positioning")

    print("\n" + "="*60)
    print("ERROR HANDLING TESTS")
    print("="*60)

    try:
        run_algorithm(board=None)
        print("✗ Null board: Should raise ValueError")
    except ValueError:
        print("✓ Null board: Correctly raises ValueError")

    try:
        run_algorithm(board=[['X', 'X', 'X'], ['O', 'O', ''], ['', '', '']])
        print("✗ Won game: Should raise InvalidBoardError")
    except InvalidBoardError:
        print("✓ Won game: Correctly raises InvalidBoardError")

    try:
        run_algorithm(board=[['X', 'X'], ['O', 'O']])
        print("✗ Wrong size: Should raise InvalidBoardError")
    except InvalidBoardError:
        print("✓ Wrong size: Correctly raises InvalidBoardError")

    try:
        run_algorithm(board=[['X', 'X', 'X'], ['O', 'O', 'O'], ['X', 'X', 'X']])
        print("✗ Invalid state: Should raise InvalidBoardError")
    except InvalidBoardError:
        print("✓ Invalid state: Correctly raises InvalidBoardError")

    print("\n" + "="*60)
    print("ALL TESTS COMPLETE")
    print("="*60)
