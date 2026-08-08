"""
Tick Bitmap — efficient search for initialized ticks.

The bitmap stores one bit per tick (adjusted by tickSpacing).
Ticks are grouped into 256-bit words indexed by word_pos (int16).

Given tick and tickSpacing:
  compressed = tick // tickSpacing
  word_pos = compressed >> 8         (which 256-bit group)
  bit_pos  = compressed & 0xFF      (position within the group, 0..255)

Corresponds to: TickBitmap.sol in Uniswap V3.
"""


class TickBitmapManager:
    """
    In-memory tick bitmap manager.
    For DB persistence, call to_dict() / from_dict().
    """

    def __init__(self, tick_spacing: int):
        self.tick_spacing = tick_spacing
        # word_pos -> 256-bit integer
        self._words: dict[int, int] = {}

    def _position(self, tick: int) -> tuple[int, int]:
        """Get (word_pos, bit_pos) for a tick."""
        assert tick % self.tick_spacing == 0, f"Tick {tick} not aligned to spacing {self.tick_spacing}"
        compressed = tick // self.tick_spacing
        word_pos = compressed >> 8
        bit_pos = compressed & 0xFF
        return word_pos, bit_pos

    def flip_tick(self, tick: int):
        """
        Toggle the initialized state of a tick.

        Corresponds to: TickBitmap.flipTick

        Called when a tick transitions from uninitialized → initialized
        or initialized → uninitialized (when liquidityGross goes to/from 0).
        """
        word_pos, bit_pos = self._position(tick)
        mask = 1 << bit_pos
        current = self._words.get(word_pos, 0)
        self._words[word_pos] = current ^ mask

    def is_initialized(self, tick: int) -> bool:
        """Check if a tick is initialized."""
        word_pos, bit_pos = self._position(tick)
        current = self._words.get(word_pos, 0)
        return bool(current & (1 << bit_pos))

    def next_initialized_tick_within_one_word(
        self, tick: int, lte: bool
    ) -> tuple[int, bool]:
        """
        Search for the next initialized tick within the current 256-bit word.

        Args:
            tick: current tick to search from
            lte: True = search left (find tick ≤ current), False = search right (find tick > current)

        Returns:
            (next_tick, initialized): the next tick and whether it's initialized

        Corresponds to: TickBitmap.nextInitializedTickWithinOneWord
        """
        # Python's // already rounds toward negative infinity for all signs
        # (unlike Solidity's `/`, which truncates toward zero and needs a
        # manual decrement for negative ticks). No further adjustment needed.
        compressed = tick // self.tick_spacing

        if lte:
            # Search left: find tick ≤ current within same word
            word_pos = compressed >> 8
            bit_pos = compressed & 0xFF

            # Mask: all 1s at or to the right of bit_pos
            # mask = (1 << (bit_pos + 1)) - 1
            mask = (1 << (bit_pos + 1)) - 1
            word = self._words.get(word_pos, 0)
            masked = word & mask

            initialized = masked != 0
            if initialized:
                # Find most significant bit (leftmost 1)
                msb = masked.bit_length() - 1
                next_compressed = (word_pos << 8) + msb
            else:
                # Return leftmost tick in this word
                next_compressed = (word_pos << 8)

            return next_compressed * self.tick_spacing, initialized
        else:
            # Search right: find tick > current within same word
            compressed += 1  # start from next tick
            word_pos = compressed >> 8
            bit_pos = compressed & 0xFF

            # Mask: all 1s at or to the left of bit_pos
            # mask = ~((1 << bit_pos) - 1) & ((1 << 256) - 1)
            mask = ((1 << 256) - 1) ^ ((1 << bit_pos) - 1)
            word = self._words.get(word_pos, 0)
            masked = word & mask

            initialized = masked != 0
            if initialized:
                # Find least significant bit (rightmost 1)
                lsb = (masked & -masked).bit_length() - 1
                next_compressed = (word_pos << 8) + lsb
            else:
                # Return rightmost tick in this word
                next_compressed = (word_pos << 8) + 255

            return next_compressed * self.tick_spacing, initialized

    def to_dict(self) -> dict[int, str]:
        """Serialize to dict for DB storage. Values are hex strings."""
        return {k: hex(v) for k, v in self._words.items() if v != 0}

    @classmethod
    def from_dict(cls, tick_spacing: int, data: dict[int, str]) -> "TickBitmapManager":
        """Deserialize from DB storage."""
        bm = cls(tick_spacing)
        bm._words = {int(k): int(v, 16) for k, v in data.items()}
        return bm
