package pygo

/*
#include <stdlib.h>
struct grail_pygo_tuple {
	int num;
	size_t data_size;
	unsigned char *data;
};

struct grail_pygo_request {
	char *func_name;
	struct grail_pygo_tuple ins;
	struct grail_pygo_tuple outs;
};
*/
import "C"

import (
	"bytes"
	"encoding/gob"
	"fmt"
	"reflect"
	"runtime/debug"
	"unsafe"
)

//export grail_pygo_call
func grail_pygo_call(req *C.struct_grail_pygo_request) (err *C.char) {
	req.outs = C.struct_grail_pygo_tuple{}

	var (
		funcName  = C.GoString(req.func_name)
		funcValue = findFunc(funcName)
	)
	if !funcValue.IsValid() {
		return C.CString(fmt.Sprintf("pygo: function %q not found (did you pygo.Register?)", funcName))
	}

	// TODO: Allow variadic?
	funcType := funcValue.Type()
	if got, want := int(req.ins.num), funcType.NumIn(); got != want {
		return C.CString(fmt.Sprintf("pygo: wrong number of arguments: got %d, want %d", got, want))
	}
	var (
		insBytes = C.GoBytes(unsafe.Pointer(req.ins.data), C.int(req.ins.data_size))
		insDec   = gob.NewDecoder(bytes.NewReader(insBytes))
		ins      = make([]reflect.Value, req.ins.num)
	)
	for i := range ins {
		ins[i] = reflect.New(funcType.In(i))
		if err := insDec.DecodeValue(ins[i]); err != nil {
			return C.CString(fmt.Sprintf("pygo: error decoding argument %d: %v", i, err))
		}
		ins[i] = ins[i].Elem()
	}

	var (
		outs         []reflect.Value
		recovered    interface{}
		recoverStack []byte
	)
	func() {
		defer func() {
			recovered = recover()
			recoverStack = debug.Stack()
		}()
		outs = funcValue.Call(ins)
	}()
	if recovered != nil {
		return C.CString(fmt.Sprintf("pygo: panic during call: %v:\n%s", recovered, recoverStack))
	}

	var (
		outsBuf bytes.Buffer
		outsEnc = gob.NewEncoder(&outsBuf)
	)
	for i, out := range outs {
		if err := outsEnc.EncodeValue(out); err != nil {
			return C.CString(fmt.Sprintf("pygo: error encoding return %d: %v", i, err))
		}
	}
	req.outs.num = C.int(len(outs))
	req.outs.data_size = C.size_t(outsBuf.Len())
	req.outs.data = (*C.uchar)(C.CBytes(outsBuf.Bytes()))

	return nil
}

// grail_pygo_free frees memory allocated by grail_pygo_call.
//export grail_pygo_free
func grail_pygo_free(req *C.struct_grail_pygo_request) {
	if req.outs == (C.struct_grail_pygo_tuple{}) {
		return
	}
	C.free(unsafe.Pointer(req.outs.data))
	req.outs = C.struct_grail_pygo_tuple{}
}
