"""Explicit SC counter adapters and exact B4 encode/restore reference entries.

The repository's existing integer/dyadic oracle is imported, not copied. Encoder
inputs are exactly 64 raw BF16 (frac=7) or FP32 (frac=23) words. All finite words,
including signed zero, subnormals and maximum finite values, are supported.
NaN/Inf encoder inputs are rejected: the historical encoder oracle only defines
finite input groups, even though the RTL also has an ``invalid`` output.

Counters have shape [4 bins][2 rails][8 weight planes]. Their representation is
mandatory. ``input_sign_twos_complement`` uses the INPUT sign as rail and -128
for plane 7; ``product_sign_magnitude`` uses the PRODUCT sign as rail and +128
for plane 7. Normalization returns four signed integers. It does NOT construct
or pretend to construct the original RTL count bus from the other convention.

Restoration follows nr_bin_restore FUSED=0: per-bin integer-to-FP32 conversion
including division by T, then FP32 weight-scale multiplication, then FP32 sum in
bin order 0,1,2,3. RNE is applied at each original rounding boundary. All FP32
weight-scale bit patterns have the existing arithmetic oracle's IEEE-style
behavior, including subnormal/zero, infinity and canonical NaN 0x7fc00000.
This permissive arithmetic domain does not approve NaN/Inf/negative model
weight scales. No timing, PPA, full-model PPL or RTL equivalence is claimed here.
"""

from collections.abc import Mapping
from functools import lru_cache
import importlib.util
from pathlib import Path


COUNT_REPRESENTATIONS = ("input_sign_twos_complement", "product_sign_magnitude")
SUPPORTED_SAMPLES = (16, 32, 64)
ROOT = Path(__file__).resolve().parents[2]


class ArithmeticContractError(ValueError):
    """An operand's declared representation, shape, range or width is invalid."""


def _require(ok, message):
    if not ok:
        raise ArithmeticContractError(message)


def _sequence(value, name):
    _require(not isinstance(value, (str, bytes, bytearray, Mapping)), name + " must be a sequence")
    try:
        return tuple(value)
    except TypeError as exc:
        raise ArithmeticContractError(name + " must be a sequence") from exc


def _unsigned(value, width, name):
    _require(type(value) is int and 0 <= value < (1 << width), name + " must be an unsigned integer word")


def _frame(inputs, samples):
    _require(type(inputs) is int and 1 <= inputs <= 64, "inputs must be an integer in 1..64")
    _require(type(samples) is int and samples in SUPPORTED_SAMPLES, "samples must be T16, T32 or T64")
    return inputs * samples


def _count_width(width, maximum):
    _require(type(width) is int and width >= maximum.bit_length(),
             "count_width cannot represent the configured full-frame endpoint")


def _accumulator_width(width, maximum):
    needed = (128 * maximum).bit_length() + 1
    if width is None:
        return needed
    _require(type(width) is int and width >= needed,
             "accumulator_width cannot represent positive W=-128/input-negative endpoint")
    return width


def _representation(name):
    _require(type(name) is str and name in COUNT_REPRESENTATIONS,
             "explicit supported count representation is required")


@lru_cache(maxsize=1)
def _oracle():
    path = ROOT / "architecture_tlm/digital_ppa_v1/sim/validate.py"
    reference = ROOT / "format_conversion_rtl_20261016/sim/reference.py"
    if not path.is_file() or not reference.is_file():
        raise ArithmeticContractError("check out both digital_ppa_v1 and format_conversion_rtl_20261016 oracle sources")
    spec = importlib.util.spec_from_file_location("encoding_restore_existing_oracle", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def encode(words, *, frac=7):
    """Return the existing encoder's fields and packed 785-bit result.

    Lane 0 occupies each field's least-significant bits. ``input_sign`` is the
    raw input sign bit (1 = negative), including negative zero; true_one is a
    separate endpoint bypass, not an extra quantization bit in q. Packed layout
    is q[511:0], bin[639:512], sign[703:640], one[767:704], exp[783:768],
    invalid[784]. No channel reordering or float-to-BF16 conversion is implicit.
    """
    _require(type(frac) is int and frac in (7, 23), "frac must select BF16=7 or FP32=23")
    words = _sequence(words, "words")
    _require(len(words) == 64, "one complete group of 64 words is required")
    for word in words:
        _unsigned(word, frac + 9, "input")
        _require(((word >> frac) & 255) != 255, "finite encoder inputs required; NaN/Inf have no numeric oracle")
    packed = _oracle().encoder(words, frac)
    exponent = (packed >> 768) & 65535
    if exponent & 32768:
        exponent -= 65536
    return dict(q=tuple((packed >> (8 * i)) & 255 for i in range(64)),
                bins=tuple((packed >> (512 + 2 * i)) & 3 for i in range(64)),
                input_sign=tuple((packed >> (640 + i)) & 1 for i in range(64)),
                true_one=tuple((packed >> (704 + i)) & 1 for i in range(64)),
                top_exp=exponent, packed=packed, invalid=False)


def normalize_counts(counts, *, representation, count_width, samples,
                     inputs=64, accumulator_width=None):
    """Normalize one output's explicitly tagged [4][2][8] counts.

    Every raw count is bounded by inputs*T and the declared unsigned width;
    signed-state width covers the configured positive endpoint. These checks
    do not prove that arbitrary per-plane counts can arise from a real shared
    sample frame. ``accumulate_counts`` constructs counts from such a frame.
    No flattening, signed-rail relabeling or hidden width truncation is allowed.
    """
    _representation(representation)
    maximum = _frame(inputs, samples)
    _count_width(count_width, maximum)
    width = _accumulator_width(accumulator_width, maximum)
    counts = _sequence(counts, "counts")
    _require(len(counts) == 4, "counts must have shape [4][2][8]")
    result = []
    for raw_bin in counts:
        rails = _sequence(raw_bin, "rails")
        _require(len(rails) == 2, "counts must have shape [4][2][8]")
        rails = tuple(_sequence(rail, "planes") for rail in rails)
        _require(all(len(rail) == 8 for rail in rails), "counts must have shape [4][2][8]")
        for rail in rails:
            for count in rail:
                _require(type(count) is int and 0 <= count <= maximum,
                         "each count must be an integer in 0..inputs*T")
                _require(count < (1 << count_width), "count does not fit declared width")
        value = sum((rails[0][p] - rails[1][p]) *
                    (-128 if p == 7 and representation == "input_sign_twos_complement" else 1 << p)
                    for p in range(8))
        _require(-(1 << (width - 1)) <= value < (1 << (width - 1)), "normalized bin does not fit signed state")
        result.append(value)
    return tuple(result)


def accumulate_counts(weights, input_sign, bins, sample_bits, *, representation,
                      count_width, true_one=None):
    """Build one output's counts from fixed W8 and an explicit accepted frame.

    Weights/sign/bin/true_one are length N (1..64); sample_bits has shape [T][N].
    The same frame is reused for either representation, with true_one overriding
    its raw bit. This helper neither generates RNG draws nor changes their order.
    A caller storing multiple outputs calls it per output with the same frame.
    """
    _representation(representation)
    weights, signs, bins = (_sequence(x, name) for x, name in
                             ((weights, "weights"), (input_sign, "input_sign"), (bins, "bins")))
    frame = _sequence(sample_bits, "sample_bits")
    n, t = len(weights), len(frame)
    maximum = _frame(n, t)
    _count_width(count_width, maximum)
    ones = (0,) * n if true_one is None else _sequence(true_one, "true_one")
    _require(len(signs) == n and len(bins) == n and len(ones) == n,
             "weights, input_sign, bins and true_one must have equal lengths")
    _require(all(type(w) is int and -128 <= w <= 127 for w in weights), "weights must be signed W8 in -128..127")
    _require(all(type(b) is int and 0 <= b < 4 for b in bins), "bin identifiers must be integers 0..3")
    frame = tuple(_sequence(row, "sample row") for row in frame)
    _require(all(len(row) == n for row in frame), "sample frame must have shape [T][N]")
    _require(all(type(bit) in (int, bool) and bit in (0, 1) for seq in (signs, ones) + frame for bit in seq),
             "sign, true_one and sample entries must be bits")
    counts = [[[0] * 8 for _ in range(2)] for _ in range(4)]
    for sample in frame:
        for w, sign, b, bit, one in zip(weights, signs, bins, sample, ones):
            if not (bit or one):
                continue
            if representation == "input_sign_twos_complement":
                rail, code = int(sign), w & 255
            else:
                rail, code = int(bool(sign) ^ (w < 0)), abs(w)
            for p in range(8):
                counts[b][rail][p] += (code >> p) & 1
    return tuple(tuple(tuple(rail) for rail in b) for b in counts)


def restore_bins(bin_sums, *, top_exp, weight_scale_word, samples,
                 inputs=64, accumulator_width=None):
    """Return one FP32 partial using FUSED=0's original rounding order.

    Four signed integers are required, not a count bus. T16/T32/T64 is explicit.
    top_exp is restricted to the range emitted for finite FP32/BF16 groups
    (-149..128); this avoids pretending arbitrary signed16 exponent arithmetic
    has been qualified. Raw FP32 scale words can produce underflow, overflow or
    NaN exactly as the imported oracle specifies. Cross-input-block addition and
    final BF16 conversion are separate operations and are not performed here.
    """
    maximum = _frame(inputs, samples)
    width = _accumulator_width(accumulator_width, maximum)
    values = _sequence(bin_sums, "bin_sums")
    _require(len(values) == 4, "exactly four signed bin integers are required")
    _require(all(type(v) is int and -(1 << (width - 1)) <= v < (1 << (width - 1)) for v in values),
             "bin sum does not fit declared signed accumulator width")
    _require(type(top_exp) is int and -149 <= top_exp <= 128, "top_exp must be in finite-group range -149..128")
    _unsigned(weight_scale_word, 32, "weight_scale_word")
    oracle = _oracle()
    result = 0
    t_log2 = samples.bit_length() - 1
    for b, integer in enumerate(values):
        value = oracle.R.pack(integer, top_exp - 2 * b - t_log2, 23)[0]
        result = oracle.add(result, oracle.mul(value, weight_scale_word))
    return result


def add_words(a, b):
    """One separate RNE FP32 addition of raw words, for cross-block reduction.

    Special values and signed zeros follow the existing exact dyadic oracle;
    no host-float conversion, fused accumulation or implicit BF16 narrowing.
    """
    _unsigned(a, 32, "a")
    _unsigned(b, 32, "b")
    return _oracle().add(a, b)
