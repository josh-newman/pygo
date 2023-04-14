package pygobigslice

import (
	"bytes"
	"flag"
	"io"
	"io/ioutil"
	"sync"

	"github.com/grailbio/base/must"
	"github.com/grailbio/bigmachine/ec2system"
	"github.com/grailbio/bigslice/exec"
	"github.com/josh-newman/pygo"
)

const systemName = "ec2pygo"

var global struct {
	mu sync.Mutex

	flags []string
	S     *exec.Session

	remoteExe []byte
}

func init() {
	pygo.Main = bigsliceMain

	// TODO: Use github.com/grailbio/base/config instead.
	// sliceflags.RegisterSystemProvider(systemName, &pygoProvider{})

	pygo.Register("pygo_bigslice_use_ec2", func(ec2Params string) {
		global.mu.Lock()
		defer global.mu.Unlock()

		must.True(global.S == nil, "bigslice session already created")
		must.True(global.remoteExe != nil, "remote exe not set, make sure `pygo_go_binary` has `bigslice = True`")

		systemFlag := "-system=" + systemName
		if len(ec2Params) > 0 {
			systemFlag += ":" + ec2Params
		}
		global.flags = append(global.flags, systemFlag)
	})

	pygo.Register("pygo_bigslice_add_flags", func(flags []string) {
		global.mu.Lock()
		defer global.mu.Unlock()

		must.Truef(global.S == nil, "bigslice session already created")

		global.flags = append(global.flags, flags...)
	})

	// TODO: For now, don't use profiles, because we want sliceflags's v23 support.
	// pygo.Register("pygo_profile_parse", func(profile string) {
	// 	config.Application().Parse(strings.NewReader(profile))
	// })
	// pygo.Register("pygo_profile_dump", func() string {
	// 	var buf bytes.Buffer
	// 	must.Nil(config.Application().PrintTo(&buf))
	// 	return buf.String()
	// })
}

func MustSession() *exec.Session {
	global.mu.Lock()
	defer global.mu.Unlock()

	if global.S == nil {
		// ctx := cgovcontext.Background()
		var (
			flags flag.FlagSet
			// sliceFlags sliceflags.Flags
		)
		// sliceflags.RegisterFlags(&flags, &sliceFlags, "")
		must.Nil(flags.Parse(global.flags))
		// execOptions, err := sliceFlags.ExecOptions(ctx)
		// must.Nil(err)
		// global.S = exec.Start(execOptions...)

		// if len(sliceFlags.HTTPAddress.Address) > 0 {
		// 	global.S.HandleDebug(http.DefaultServeMux)
		// 	http.Handle("/debug/status", status.Handler(global.S.Status()))
		// 	go func() {
		// 		log.Printf("HTTP Status at: %v\n", sliceFlags.HTTPAddress)
		// 		must.Nil(http.ListenAndServe(sliceFlags.HTTPAddress.Address, nil))
		// 	}()
		// }
		// TODO: session.Shutdown()?
	}

	return global.S
}

// type pygoProvider struct {
// 	ec2 sliceflags.EC2
// }

// func (p *pygoProvider) Name() string       { return systemName }
// func (p *pygoProvider) Set(s string) error { return p.ec2.Set(s) }

// func (p *pygoProvider) ExecutorConf(ctx *context.T) (sliceflags.ExecutorConf, error) {
// 	system, params, err := p.ec2.NewSystem(ctx)
// 	if err != nil {
// 		return sliceflags.ExecutorConf{}, err
// 	}
// 	// Requires D55072.
// 	params = append(params, bigmachine.MachineExe(pygoRemoteExe))
// 	return sliceflags.ExecutorConf{
// 		ExecOption:         exec.Bigmachine(system, params...),
// 		DefaultParallelism: runtime.GOMAXPROCS(0),
// 		Eventer:            system.Eventer,
// 	}, nil
// }

func InternalSetRemoteExe(e []byte) {
	must.Truef(len(e) > 0, "remote exe must be non-empty")

	global.mu.Lock()
	defer global.mu.Unlock()

	must.Truef(global.remoteExe == nil, "remote exe already set")
	global.remoteExe = append([]byte{}, e...)
}

func pygoRemoteExe(goos, goarch string) (_ io.ReadCloser, size int64, _ error) {
	must.True(goos == "linux" && goarch == "amd64", "only linux amd64 is supported, got %s %s", goos, goarch)

	global.mu.Lock()
	defer global.mu.Unlock()

	return ioutil.NopCloser(bytes.NewReader(global.remoteExe)), int64(len(global.remoteExe)), nil
}

// isRemoteExe is a bool: "true" == true, otherwise false.
var isRemoteExe string

// bigsliceMain replaces pygo.Main.
func bigsliceMain() {
	if isRemoteExe != "true" {
		// Local execution (.so loaded as a Python module) doesn't do anything.
		return
	}
	// Remote execution spawns the bigmachine server.
	// _ = cgovcontext.Background()
	var system ec2system.System
	_ = exec.Start(exec.Bigmachine(&system))
	panic("didn't expect to get here!")
}
