package counting

import (
	"github.com/grailbio/base/must"
	"github.com/josh-newman/pygo/pygonumpy"
)

type Int64s []int64

func (ints *Int64s) Reset() {
	for i := range *ints {
		(*ints)[i] = 0
	}
	*ints = (*ints)[:0]
}

// At returns a pointer to ints[idx], enlarging if necessary.
func (ints *Int64s) At(idx int) *int64 {
	must.True(idx >= 0)
	ints.ensure(idx + 1)
	return &(*ints)[idx]
}

func (ints *Int64s) Add(o Int64s) {
	ints.ensure(len(o))
	for i := range *ints {
		if i >= len(o) {
			break
		}
		(*ints)[i] += o[i]
	}
}

func (ints *Int64s) ensure(n int) {
	short := n - len(*ints)
	if short <= 0 {
		return
	}
	*ints = append(*ints, make(Int64s, short)...)
}

func (ints Int64s) Max() int64 {
	var max int64 = -1
	for _, elem := range ints {
		if elem > max {
			max = elem
		}
	}
	return max
}

func (ints Int64s) GobEncode() ([]byte, error) {
	return pygonumpy.Int64s(ints).MarshalBinary()
}

func (ints *Int64s) GobDecode(bs []byte) error {
	return ((*pygonumpy.Int64s)(ints)).UnmarshalBinary(bs)
}
