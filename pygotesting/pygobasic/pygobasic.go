package main

import (
	"encoding/gob"
	"fmt"
	"math"
	"reflect"
	"strings"

	"github.com/google/go-cmp/cmp"
	"github.com/grailbio/base/backgroundcontext"
	"github.com/grailbio/base/file"
	"github.com/grailbio/base/must"
	"github.com/josh-newman/pygo"
	"github.com/josh-newman/pygo/pygonumpy"
	"github.com/josh-newman/pygo/pygotesting/pygobasic/counting"
)

func init() {
	pygo.Register("math.Abs", math.Abs)
	pygo.Register("strings.Contains", strings.Contains)
	pygo.Register("strings.HasPrefix", strings.HasPrefix)
	pygo.Register("strings.HasSuffix", strings.HasSuffix)

	pygo.Register("test_ListS3", func(dir string) []string {
		// ctx := cgovcontext.Background()
		ctx := backgroundcontext.Get()
		lister := file.List(ctx, "s3://commoncrawl/", false)
		var items []string
		for lister.Scan() {
			items = append(items, lister.Path())
		}
		if err := lister.Err(); err != nil {
			panic(err)
		}
		return items
	})

	type test1 struct {
		A int
		B int
		C string
	}
	gob.RegisterName("pygo_test1", test1{})
	// testObjs corresponds to the test list in new_test.py.
	testObjs := [][]interface{}{
		{0},
		{3},
		{127},
		{128},
		{220},
		{32983},
		{-3},
		{-127},
		{-128},
		{-220},
		{-32983},
		{true},
		{false},
		{true},
		{0.0},
		{1.0},
		{-1.0},
		{-1.5},
		{1.5},
		{3.14159265358979323846264338327950288419716939937510582097494459},
		{math.Inf(1)},
		{math.Inf(-1)},
		{""},
		{"hello"},
		{"@&*X("},
		{"a\t \nb"},
		{[]int{7, 8, 9}},
		{[]string{"A", "B"}},
		{map[string]int{"a": 1, "b": 2}},
		{[]string{"a"}, 1},
		{map[string]int{"a": 1, "b": 2}, 3.},
		{func() interface{} {
			var i interface{} = "hello"
			return &i
		}()},
		{counting.Int64s{1, 2, 3}},
		{pygonumpy.Float64s{4., 5.6, 7.8}},
		{test1{A: 1, C: "2"}},
		{func() interface{} {
			var i interface{} = test1{A: 3, B: 7}
			return &i
		}()},
	}
	for testIdx, objs := range testObjs {
		var (
			objs      = objs
			objTypes  = make([]reflect.Type, len(objs))
			objValues = make([]reflect.Value, len(objs))
		)
		for i, obj := range objs {
			objTypes[i] = reflect.TypeOf(obj)
			objValues[i] = reflect.ValueOf(obj)
		}
		pygo.Register(fmt.Sprintf("test_gorecv_%d", testIdx), reflect.MakeFunc(
			reflect.FuncOf(objTypes, nil, false),
			func(gots []reflect.Value) []reflect.Value {
				must.True(len(gots) == len(objs))
				for i := range gots {
					got, want := gots[i].Interface(), objs[i]
					must.Truef(cmp.Equal(got, want),
						"case %d: got %v [%[2]T], want %v [%[3]T]", testIdx, got, want)
				}
				return nil
			},
		).Interface())
		pygo.Register(fmt.Sprintf("test_gosend_%d", testIdx), reflect.MakeFunc(
			reflect.FuncOf(nil, objTypes, false),
			func([]reflect.Value) []reflect.Value { return objValues },
		).Interface())
	}
	pygo.Register("test_gorecv_nan", func(got float64) {
		must.Truef(math.IsNaN(got), "float got %f, want NaN", got)
	})
}

func main() { pygo.Main() }
