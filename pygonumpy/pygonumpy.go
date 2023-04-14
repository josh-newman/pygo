package pygonumpy

import (
	"bytes"
	"compress/gzip"
	"io"

	"github.com/grailbio/base/must"
	"github.com/kshedden/gonpy"
)

type (
	Int64s   []int64
	Float64s []float64
)

const prefixNumPy = "pygo.numpy:"

func (ints Int64s) MarshalBinary() ([]byte, error) {
	var buf bytes.Buffer
	npyW := newGzNpyW(&buf, len(ints))
	must.Nil(npyW.WriteInt64(ints))
	return buf.Bytes(), nil
}

func (ints *Int64s) UnmarshalBinary(gobbed []byte) error {
	npyR, close := newGzNpyR(gobbed)
	var err error
	*ints, err = npyR.GetInt64()
	close()
	return err
}

func (fs Float64s) MarshalBinary() ([]byte, error) {
	var buf bytes.Buffer
	npyW := newGzNpyW(&buf, len(fs))
	must.Nil(npyW.WriteFloat64(fs))
	return buf.Bytes(), nil
}

func (fs *Float64s) UnmarshalBinary(gobbed []byte) error {
	npyR, close := newGzNpyR(gobbed)
	var err error
	*fs, err = npyR.GetFloat64()
	close()
	return err
}

func newGzNpyW(w io.Writer, len int) *gonpy.NpyWriter {
	_, err := w.Write([]byte(prefixNumPy))
	must.Nil(err)
	gzW := gzip.NewWriter(w)
	npyW, err := gonpy.NewWriter(gzW)
	must.Nil(err)
	npyW.Shape = []int{len}
	return npyW
}

func newGzNpyR(gobbed []byte) (_ *gonpy.NpyReader, close func()) {
	if !bytes.HasPrefix(gobbed, []byte(prefixNumPy)) {
		panic("not a NumPyInt64s")
	}
	gobbed = gobbed[len(prefixNumPy):]
	gzR, err := gzip.NewReader(bytes.NewReader(gobbed))
	must.Nil(err)
	npyR, err := gonpy.NewReader(gzR)
	must.Nil(err)
	return npyR, func() { must.Nil(gzR.Close()) }
}
