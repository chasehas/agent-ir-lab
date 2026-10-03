// Workaround for Falco on VMs where root lacks CAP_SYS_RESOURCE (e.g. Claude Code cloud sessions).
// Falco's modern_ebpf driver tries to raise RLIMIT_MEMLOCK and exits if it can't. Kernels >= 5.11
// charge BPF memory to the memory cgroup, not memlock, so pretending the call succeeded is safe there.
// Build: gcc -shared -fPIC -O2 -o nomemlock.so nomemlock.c -ldl
// Used by capture.sh automatically when nomemlock.so exists next to this file.
#define _GNU_SOURCE
#include <dlfcn.h>
#include <sys/resource.h>

typedef int (*setrlimit_fn)(__rlimit_resource_t, const struct rlimit *);

int setrlimit(__rlimit_resource_t resource, const struct rlimit *limit) {
  if (resource == RLIMIT_MEMLOCK) return 0;
  return ((setrlimit_fn)dlsym(RTLD_NEXT, "setrlimit"))(resource, limit);
}

int setrlimit64(__rlimit_resource_t resource, const struct rlimit64 *limit) {
  return setrlimit(resource, (const struct rlimit *)limit);
}
