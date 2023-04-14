package pygo

import (
	"fmt"
	"reflect"
	"sync"
)

var (
	funcs  = map[string]reflect.Value{}
	funcMu sync.Mutex
)

func Register(name string, f interface{}) {
	v := reflect.ValueOf(f)
	if v.Type().Kind() != reflect.Func {
		panic(fmt.Sprintf("pygo: Register argument must be func, got: %T", f))
	}
	funcMu.Lock()
	defer funcMu.Unlock()
	if _, ok := funcs[name]; ok {
		panic(fmt.Sprintf("pygo: duplicate Register for name: %s", name))
	}
	funcs[name] = v
}

func findFunc(name string) reflect.Value {
	funcMu.Lock()
	defer funcMu.Unlock()
	return funcs[name]
}

// Main should be called in the `main` function of pygo binaries:
//   func main() { pygo.Main() }
//
// Details: For non-bigslice execution, Main does nothing, and is just a placeholder for the
// .so output. However, in bigslice execution, the remote executable has a non-trivial, which
// is installed here. Users don't need to worry about that, though.
var Main = func() {}
