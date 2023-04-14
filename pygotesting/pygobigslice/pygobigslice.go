package main

import (
	"fmt"

	"github.com/grailbio/base/backgroundcontext"
	"github.com/grailbio/base/file"
	"github.com/grailbio/base/must"
	"github.com/grailbio/bigslice"
	"github.com/josh-newman/pygo"
	"github.com/josh-newman/pygo/pygobigslice"
)

var stat = bigslice.Func(func(paths []string) bigslice.Slice {
	slice := bigslice.Const(len(paths), paths)
	return bigslice.Map(slice, func(path string) (_, stat string) {
		info, err := file.Stat(backgroundcontext.Get(), path)
		must.Nil(err)
		return path, fmt.Sprintf("[size: %v, mod: %v]", info.Size(), info.ModTime())
	})
})

func init() {
	pygo.Register("pygo_bigslice_demo_stat", func(paths []string) map[string]string {
		// ctx := cgovcontext.Background()
		ctx := backgroundcontext.Get()
		result, err := pygobigslice.MustSession().Run(ctx, stat, paths)
		must.Nil(err)
		scanner := result.Scanner()
		var (
			path, stat string
			results    = map[string]string{}
		)
		for scanner.Scan(ctx, &path, &stat) {
			results[path] = stat
		}
		must.Nil(scanner.Err())
		must.Nil(scanner.Close())
		return results
	})
}

func main() { pygo.Main() }
