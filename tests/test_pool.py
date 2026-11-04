import pytest

from pool import KeyPool


def test_overflow_is_counted_as_wasted():
    pool = KeyPool(capacity=1000, stock=900)
    pool.add(300)
    assert pool.stock == 1000
    assert pool.wasted == 200


def test_cannot_take_more_than_the_stock():
    pool = KeyPool(capacity=1000, stock=100)
    with pytest.raises(ValueError):
        pool.take(101, "otp")


def test_bits_are_conserved():
    pool = KeyPool(capacity=1000, stock=500)
    for bits in (700, 300, 900):
        pool.add(bits)
        pool.take(450, "otp")
        pool.take(10, "aes")
    assert pool.initial + pool.generated == pytest.approx(pool.total_used + pool.wasted + pool.stock)
    assert pool.stock >= 0
