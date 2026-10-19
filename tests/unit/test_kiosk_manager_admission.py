"""Compiled production manager proof with real proc/pidfds and bounded bus doubles.

All writes/builds use pytest-private scratch. Compiler/probes are bounded waited
children; the exec witness owns its child through a pidfd and pipe barriers and
never signals another process. No live bus, namespace mutation or service runs.
Acquisition uses narrow loader, system-manager namespace and role-owner doubles;
selected proof is then checked across real child exec/exit and thread census.
"""
from pathlib import Path
import subprocess

import pytest

from tools import test_storage


ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def manager_probe(tmp_path_factory):
    directory = tmp_path_factory.mktemp("manager-native")
    source = directory / "manager.c"
    binary = directory / "manager"
    source.write_text(r'''
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <dirent.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <stdarg.h>
#include <unistd.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <sys/syscall.h>
#include <time.h>
#include <dlfcn.h>
#include <pthread.h>
struct kiosk_failure { const char *stage, *reason; int error; };
struct kiosk_pin_namespace { int fd; dev_t device; ino_t inode; };
static void kiosk_failure(struct kiosk_failure *f,const char *s,const char *r,int e) {
    if (!f->stage) { f->stage=s; f->reason=r; f->error=e; }
}
static void require(int v,const char *s) {
    if(!v) { fprintf(stderr,"manager-witness:%s:%s\n",s,strerror(errno)); exit(1); }
}
static void proof_require(int value,const struct kiosk_failure *failure,const char *stage) {
    if(!value)fprintf(stderr,"native-proof:%s:%s:%d\n",failure->stage?failure->stage:"none",
                     failure->reason?failure->reason:"none",failure->error);
    require(value,stage);
}
static int kiosk_path(const char *p,int absolute) {
    return (absolute ? p[0]=='/' : p[0]!='/') && !strstr(p,"..") && !strstr(p,"//");
}
static int kiosk_pin_open(int fd,const char *path) {
    (void)fd; (void)path; return open("marker",O_PATH|O_CLOEXEC);
}
static const char *fault;
static int status_calls;
static int acquiring;
static int dynamic_task_status;
static uint32_t witness_pid;
static ino_t fixture_executable_inode;
static dev_t fixture_executable_device;
static void *controlled_dlopen(const char *,int);
static void *controlled_dlsym(void *,const char *);
static int controlled_dlclose(void *);
static int controlled_stat(const char *path,struct stat *info) {
    const char *actual=path;
    if(!strcmp(path,"/proc/1/root"))actual="/";
    if(!strcmp(path,"/proc/1/ns/user"))actual="/proc/self/ns/user";
    if(!strcmp(path,"/proc/1/ns/pid"))actual="/proc/self/ns/pid";
    int result=stat(actual,info);
    /* Only the host namespace witness is distinguished, standing in for the
     * manager's supported private mount namespace without a host mutation. */
    if(result==0 && acquiring && !strcmp(path,"/proc/self/ns/mnt")) info->st_ino++;
    return result;
}
static int controlled_fstat(int fd,struct stat *info) {
    int result=fstat(fd,info);struct stat marker;
    /* Only the private marker's owner is doubled. Kernel inode, mode, bytes,
     * timestamps and descriptor identity remain independently observed. */
    if(result==0 && stat("marker",&marker)==0 && info->st_dev==marker.st_dev && info->st_ino==marker.st_ino)
        info->st_uid=0;
    if(result==0 && info->st_dev==fixture_executable_device && info->st_ino==fixture_executable_inode)
        info->st_uid=0;
    return result;
}
static int controlled_openat(int dir,const char *path,int flags,...) {
    if (!strcmp(path,"attr/apparmor/current") || !strcmp(path,"attr/current"))
        return open("label",flags);
    if (!strcmp(path,"cgroup")) return open("cgroup",flags);
    if (!strcmp(path,"status")) {
        status_calls++;
        if (fault && !strcmp(fault,"late-credentials") && status_calls > 1)
            return open("privileged-status",flags);
        if(dynamic_task_status) {
            char stat_text[8192],status[1024];
            int stat_fd=openat(dir,"stat",O_RDONLY|O_CLOEXEC);require(stat_fd>=0,"task-status-witness");
            ssize_t n=read(stat_fd,stat_text,sizeof(stat_text)-1);close(stat_fd);require(n>0,"task-stat-read");stat_text[n]=0;
            long tid=strtol(stat_text,NULL,10);unsigned long uid=getuid(),gid=getgid();
            snprintf(status,sizeof(status),"Pid:\t%ld\nTgid:\t%u\nUid:\t%lu\t%lu\t%lu\t%lu\nGid:\t%lu\t%lu\t%lu\t%lu\nGroups:\t\nCapInh:\t0\nCapPrm:\t0\nCapEff:\t0\nCapAmb:\t0\n",
                     tid,witness_pid,uid,uid,uid,uid,gid,gid,gid,gid);
            int out=open("status",O_WRONLY|O_CREAT|O_TRUNC|O_CLOEXEC,0644);
            require(out>=0 && write(out,status,strlen(status))==(ssize_t)strlen(status) && close(out)==0,"task-identity-double");
        }
        return open("status",flags);
    }
    if (!strcmp(path,"root/usr/share/oh-no-parent-control/confinement/retained-view"))
        return open("marker",flags);
    if (fault && !strcmp(fault,"missing-task") && !strcmp(path,"stat")) {errno=ENOENT;return -1;}
    return openat(dir,path,flags);
}
#define openat controlled_openat
#define fstat controlled_fstat
#define stat(...) controlled_stat(__VA_ARGS__)
#define dlopen controlled_dlopen
#define dlsym controlled_dlsym
#define dlclose controlled_dlclose
''' + f'#include "{ROOT / "tools/kiosk_manager_admission.h"}"\n' + r'''
#undef openat
#undef fstat
#undef stat
#undef dlopen
#undef dlsym
#undef dlclose
struct sd_bus { int unused; };
struct sd_bus_message { const char *property; };
static struct sd_bus_message request,reply;
static struct kiosk_manager_proof *current;
static uint64_t previous_timeout;
static unsigned calls;
static unsigned char witness_invocation[16];
static const char *witness_cgroup="/user.slice/user-1000.slice/user@1000.service";
static int owned_bus_fd=-1, loader_opened, loader_closed;
static int new_call(struct sd_bus *b,struct sd_bus_message **m,const char *dest,const char *path,const char *iface,const char *method) {
    (void)b;
    char expected[128]; snprintf(expected,sizeof(expected),"/org/freedesktop/systemd1/unit/user_40%lu_2eservice",(unsigned long)current->uid);
    require(!strcmp(dest,"org.freedesktop.systemd1") && !strcmp(path,expected) &&
            !strcmp(iface,"org.freedesktop.DBus.Properties") && !strcmp(method,"Get"),"fixed-bus-target");
    *m=&request;return 0;
}
static int append(struct sd_bus_message *m,const char *signature,...) {
    va_list args;va_start(args,signature);
    const char *iface=va_arg(args,const char *),*property=va_arg(args,const char *);
    require(!strcmp(signature,"ss"),"bus-signature");
    require(!strcmp(iface, (!strcmp(property,"MainPID") || !strcmp(property,"ControlGroup")) ?
                       "org.freedesktop.systemd1.Service":"org.freedesktop.systemd1.Unit"),"property-interface");
    m->property=property;va_end(args);return 1;
}
static int bus_call(struct sd_bus *b,struct sd_bus_message *m,uint64_t timeout,void *error,struct sd_bus_message **out) {
    (void)b;(void)error;
    require(timeout>0 && timeout<=5000000,"bounded-call");
    if(calls%4) require(timeout<=previous_timeout,"aggregate-query-budget");
    calls++;previous_timeout=timeout;
    if (fault && !strcmp(fault,"bus-error")) return -EIO;
    reply.property=m->property;*out=&reply;return 1;
}
static int enter(struct sd_bus_message *m,char type,const char *contents) {
    require(type=='v',"variant-type");
    require(!strcmp(contents,!strcmp(m->property,"InvocationID")?"ay":!strcmp(m->property,"MainPID")?"u":"s"),"variant-content");
    return fault && !strcmp(fault,"wrong-type") ? -ENXIO:1;
}
static int leave(struct sd_bus_message *m) {(void)m;return 1;}
static int at_end(struct sd_bus_message *m,int complete) {(void)m;(void)complete;return 1;}
static int read_value(struct sd_bus_message *m,const char *signature,...) {
    va_list args;va_start(args,signature);void *out=va_arg(args,void *);va_end(args);
    if(!strcmp(signature,"u")) *(uint32_t *)out=witness_pid + (fault && !strcmp(fault,"mainpid"));
    else if(!strcmp(m->property,"ActiveState")) *(const char **)out=fault && !strcmp(fault,"inactive")?"activating":
            fault && !strcmp(fault,"reloading")?"reloading":"active";
    else *(const char **)out=fault && !strcmp(fault,"unit-cgroup")?"/different":witness_cgroup;
    return 1;
}
static int array(struct sd_bus_message *m,char type,const void **data,size_t *size) {
    (void)m;require(type=='y',"invocation-byte-array");
    static unsigned char bytes[16];memcpy(bytes,witness_invocation,16);
    if(fault && !strcmp(fault,"invocation"))bytes[0]^=1;
    if(fault && !strcmp(fault,"zero-invocation"))memset(bytes,0,16);
    *data=bytes;*size=fault && !strcmp(fault,"short-invocation")?15:16;return 1;
}
static struct sd_bus_message *message_unref(struct sd_bus_message *m){(void)m;return NULL;}
static int bus_fd(struct sd_bus *b){return b?owned_bus_fd:current->pidfd;}
static int new_bus(struct sd_bus **out) {
    static struct sd_bus bus;
    if(fault && !strcmp(fault,"bus-create"))return -ENOMEM;
    owned_bus_fd=open("/dev/null",O_RDONLY|O_CLOEXEC);*out=&bus;return owned_bus_fd>=0?0:-errno;
}
static int set_address(struct sd_bus *b,const char *address) {
    (void)b;require(!strcmp(address,"unix:path=/run/dbus/system_bus_socket"),"fixed-system-bus-address");return 0;
}
static int set_client(struct sd_bus *b,int client) {(void)b;require(client==1,"bus-client");return 0;}
static int start_bus(struct sd_bus *b) {(void)b;return fault && !strcmp(fault,"bus-start")?-EIO:0;}
static struct sd_bus *unref_bus(struct sd_bus *b) {
    (void)b;if(owned_bus_fd>=0)close(owned_bus_fd);owned_bus_fd=-1;return NULL;
}
static void *controlled_dlopen(const char *path,int flags) {
    require(!strcmp(path,"libsystemd.so.0") && flags==(RTLD_NOW|RTLD_LOCAL),"fixed-systemd-library");
    if(fault && !strcmp(fault,"bus-library"))return NULL;
    loader_opened++;return &request;
}
static int controlled_dlclose(void *library) {require(library==&request,"owned-loader-close");loader_closed++;return 0;}
static void *controlled_dlsym(void *library,const char *name) {
    require(library==&request,"owned-loader-symbol");
    if(fault && !strcmp(fault,"bus-symbol"))return NULL;
#define SYMBOL(n,f) if(!strcmp(name,n))return (void *)(f)
    SYMBOL("sd_bus_new",new_bus);SYMBOL("sd_bus_set_address",set_address);
    SYMBOL("sd_bus_set_bus_client",set_client);SYMBOL("sd_bus_start",start_bus);
    SYMBOL("sd_bus_get_fd",bus_fd);SYMBOL("sd_bus_unref",unref_bus);
    SYMBOL("sd_bus_message_new_method_call",new_call);SYMBOL("sd_bus_message_append",append);
    SYMBOL("sd_bus_call",bus_call);SYMBOL("sd_bus_message_enter_container",enter);
    SYMBOL("sd_bus_message_exit_container",leave);SYMBOL("sd_bus_message_read",read_value);
    SYMBOL("sd_bus_message_read_array",array);SYMBOL("sd_bus_message_at_end",at_end);
    SYMBOL("sd_bus_message_unref",message_unref);
#undef SYMBOL
    require(0,"known-bus-symbol");return NULL;
}
static void put(const char *path,const char *text) {
    int fd=open(path,O_WRONLY|O_CREAT|O_TRUNC|O_CLOEXEC,0644);
    require(fd>=0 && write(fd,text,strlen(text))==(ssize_t)strlen(text) && close(fd)==0,"fixture-write");
}
static unsigned descriptors(void) {
    DIR *d=opendir("/proc/self/fd");require(d!=NULL,"count-fds");unsigned n=0;struct dirent *e;
    while((e=readdir(d)))if(strcmp(e->d_name,".") && strcmp(e->d_name,".."))n++;
    closedir(d);return n;
}
static const char *digest="0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef";
static void setup(struct kiosk_manager_proof *p) {
    memset(p,0,sizeof(*p));p->proc=p->pidfd=p->root=p->usr=p->executable=p->marker=p->mount_namespace.fd=-1;
    p->uid=getuid();p->gid=getgid();p->unit.pid=getpid();p->unit.invocation[0]=1;
    witness_pid=getpid();memset(witness_invocation,0,sizeof(witness_invocation));witness_invocation[0]=1;
    p->deadline=kiosk_manager_now()+60000000;
    strcpy(p->unit.cgroup,"/user.slice/user-1000.slice/user@1000.service");
    strcpy(p->cgroup,"/user.slice/user-1000.slice/user@1000.service/init.scope");
    p->connection.new_call=new_call;p->connection.append=append;p->connection.call=bus_call;
    p->connection.enter=enter;p->connection.exit=leave;p->connection.read=read_value;p->connection.array=array;
    p->connection.at_end=at_end;p->connection.message_unref=message_unref;p->connection.get_fd=bus_fd;
    current=p;
    p->pidfd=syscall(SYS_pidfd_open,getpid(),0);
    p->proc=open("/proc/self",O_PATH|O_DIRECTORY|O_CLOEXEC);
    require(p->pidfd>=0 && p->proc>=0,"real-proc-and-pidfd");
    p->root=kiosk_manager_pin_object(p->proc,"root",O_PATH|O_DIRECTORY,&p->root_info);
    p->usr=kiosk_manager_pin_object(p->root,"usr",O_PATH|O_DIRECTORY,&p->usr_info);
    p->executable=kiosk_manager_pin_object(p->proc,"exe",O_RDONLY,&p->executable_info);
    struct stat ns;
    p->mount_namespace.fd=kiosk_manager_pin_object(p->proc,"ns/mnt",O_RDONLY,&ns);
    p->mount_namespace.device=ns.st_dev;p->mount_namespace.inode=ns.st_ino;
    require(stat("/proc/self/ns/user",&p->user_namespace)==0 && stat("/proc/self/ns/pid",&p->pid_namespace)==0,"real-namespaces");
    require(kiosk_manager_text(AT_FDCWD,"/proc/sys/kernel/random/boot_id",p->boot,sizeof(p->boot))>0,"real-boot");
    pid_t tids[KIOSK_MANAGER_TASKS];unsigned n;
    require(kiosk_manager_census(p,tids,&n)==0 && n==1,"real-task-census");
    p->count=n;p->tasks[0].tid=tids[0];
    char path[64];snprintf(path,sizeof(path),"task/%ld",(long)tids[0]);
    p->tasks[0].fd=kiosk_manager_pin_object(p->proc,path,O_PATH|O_DIRECTORY,&p->tasks[0].proc);
    require(kiosk_manager_start(p->tasks[0].fd,tids[0],&p->tasks[0].start)==0,"real-task-start");
    char status[1024];snprintf(status,sizeof(status),"Pid:\t%ld\nTgid:\t%ld\nUid:\t%lu\t%lu\t%lu\t%lu\nGid:\t%lu\t%lu\t%lu\t%lu\nGroups:\t\nCapInh:\t0\nCapPrm:\t0\nCapEff:\t0\nCapAmb:\t0\n",
       (long)getpid(),(long)getpid(),(unsigned long)p->uid,(unsigned long)p->uid,(unsigned long)p->uid,(unsigned long)p->uid,
       (unsigned long)p->gid,(unsigned long)p->gid,(unsigned long)p->gid,(unsigned long)p->gid);
    put("status",status);strcat(status,"CapEff:\t1\n");put("privileged-status",status);
    put("label","onpc-kiosk-manager (enforce)\n");
    put("cgroup","0::/user.slice/user-1000.slice/user@1000.service/init.scope\n");
    char marker[256];snprintf(marker,sizeof(marker),"ONPC-KIOSK-VIEW\t1\tapparmor\t%s\t%s\n",digest,digest);put("marker",marker);
    p->acquired=1;
}
static void exec_witness(const char *program,const char *other) {
    int ready[2],release[2];require(pipe(ready)==0 && pipe(release)==0,"exec-pipes");
    pid_t child=fork();require(child>=0,"owned-child");
    if(!child) {
        close(ready[0]);close(release[1]);
        char a[32],b[32];snprintf(a,sizeof(a),"%d",ready[1]);snprintf(b,sizeof(b),"%d",release[0]);
        char token;require(write(ready[1],"a",1)==1 && read(release[0],&token,1)==1,"before-exec-barrier");
        execl(other,other,"exec-child",a,b,NULL);_exit(127);
    }
    close(ready[1]);close(release[0]);int pidfd=syscall(SYS_pidfd_open,child,0);
    char path[64],token;snprintf(path,sizeof(path),"/proc/%ld",(long)child);
    int proc=open(path,O_PATH|O_DIRECTORY|O_CLOEXEC);require(pidfd>=0 && proc>=0 && read(ready[0],&token,1)==1,"child-identity-recorded");
    unsigned long long before,after;struct stat old,new;
    require(kiosk_manager_start(proc,child,&before)==0 && fstatat(proc,"exe",&old,0)==0,"before-exec-observation");
    struct kiosk_manager_proof proof;struct kiosk_failure failure={0};
    setup(&proof);kiosk_manager_release(&proof);current=&proof;witness_pid=child;dynamic_task_status=1;acquiring=1;
    int expected=openat(proc,"exe",O_RDONLY|O_CLOEXEC),marker=open("marker",O_RDONLY|O_CLOEXEC);
    require(expected>=0 && marker>=0,"independent-source-descriptors");
    proof_require(kiosk_manager_acquire(&proof,getuid(),getgid(),NULL,0,0,&failure)==0,&failure,"child-manager-acquired");
    require(kiosk_manager_select(&proof,expected,marker,digest,digest,&failure)==0 &&
            kiosk_manager_recheck(&proof,&failure)==0,"child-manager-selected");
    require(write(release[1],"x",1)==1 && read(ready[0],&token,1)==1 && token=='b',"after-exec-barrier");
    require(kiosk_manager_start(proc,child,&after)==0 && before==after && fstatat(proc,"exe",&new,0)==0,"exec-lifetime-preserved");
    require(kiosk_manager_file_same(&old,&new)==(!strcmp(program,other)),"exec-inode-distinguished");
    require((kiosk_manager_recheck(&proof,&failure)==0)==(!strcmp(program,other)),"selected-manager-reexec-proof");
    struct pollfd lifetime={.fd=pidfd,.events=POLLIN};require(poll(&lifetime,1,0)==0,"pidfd-cannot-detect-exec");
    require(write(release[1],"x",1)==1,"owned-exit-release");int status;
    require(waitpid(child,&status,0)==child && WIFEXITED(status) && WEXITSTATUS(status)==0,"owned-child-reaped");
    require(poll(&lifetime,1,0)==1 && (lifetime.revents&POLLIN),"exit-observed-after-exec");
    if(!strcmp(program,other))require(kiosk_manager_recheck(&proof,&failure)!=0,"selected-manager-exit-refused");
    char magic[4];require(pread(expected,magic,sizeof(magic),0)==4 && !memcmp(magic,"\177ELF",4),"source-survives-manager-exit");
    kiosk_manager_release(&proof);close(expected);close(marker);
    require(loader_opened==loader_closed && owned_bus_fd==-1,"child-bus-cleaned");
    close(ready[0]);close(release[1]);close(proc);close(pidfd);
}
static void acquire_witness(const char *mode) {
    struct kiosk_manager_proof proof;struct kiosk_failure failure={0};
    setup(&proof);kiosk_manager_release(&proof);current=&proof;acquiring=1;fault=mode;calls=0;
    if(!strcmp(mode,"acquire-missing-task"))fault="missing-task";
    if(!strcmp(mode,"acquire-wrong-label"))put("label","onpc-kiosk-manager (complain)\n");
    uid_t uid=getuid();gid_t gid=getgid();gid_t groups[2]={777,777};unsigned count=0;
    if(!strcmp(mode,"acquire-zero-uid"))uid=0;
    if(!strcmp(mode,"acquire-zero-gid"))gid=0;
    if(!strcmp(mode,"acquire-duplicate-groups"))count=2;
    uint64_t deadline=!strcmp(mode,"acquire-expired-deadline")?kiosk_manager_now()-1:
        !strcmp(mode,"acquire-shared-deadline")?kiosk_manager_now()+5000000:0;
    int result=kiosk_manager_acquire_until(&proof,uid,gid,count?groups:NULL,count,0,deadline,&failure);
    if(!strcmp(mode,"acquire-healthy") || !strcmp(mode,"acquire-shared-deadline")) {
        proof_require(result==0,&failure,"production-acquire");
        if(deadline)require(proof.deadline==deadline,"shared-transaction-deadline");
        int marker=open("marker",O_RDONLY|O_CLOEXEC);
        require(marker>=0 && kiosk_manager_select(&proof,proof.executable,marker,digest,digest,&failure)==0 &&
                kiosk_manager_recheck(&proof,&failure)==0,"acquired-proof-selected");close(marker);
    } else require(result!=0 && failure.stage!=NULL && !proof.acquired,"acquisition-refused-and-released");
    kiosk_manager_release(&proof);kiosk_manager_release(&proof);
    require(loader_opened==loader_closed && owned_bus_fd==-1,"acquisition-bus-cleaned");
}
static int thread_ready[2],thread_release[2];
static void *held_thread(void *arg) {
    (void)arg;char token;require(write(thread_ready[1],"t",1)==1 && read(thread_release[0],&token,1)==1,"thread-barriers");return NULL;
}
static void thread_witness(int remove) {
    struct kiosk_manager_proof proof;struct kiosk_failure failure={0};setup(&proof);kiosk_manager_release(&proof);current=&proof;
    acquiring=1;dynamic_task_status=1;
    require(pipe(thread_ready)==0 && pipe(thread_release)==0,"thread-pipes");pthread_t thread;char token;
    if(remove)require(pthread_create(&thread,NULL,held_thread,NULL)==0 && read(thread_ready[0],&token,1)==1,"initial-thread-ready");
    proof_require(kiosk_manager_acquire(&proof,getuid(),getgid(),NULL,0,0,&failure)==0,&failure,"thread-manager-acquired");
    require(proof.count==(remove?2:1),"complete-initial-task-census");
    int marker=open("marker",O_RDONLY|O_CLOEXEC);
    require(marker>=0 && kiosk_manager_select(&proof,proof.executable,marker,digest,digest,&failure)==0,"thread-manager-selected");
    if(remove)require(write(thread_release[1],"x",1)==1 && pthread_join(thread,NULL)==0,"initial-thread-retired");
    else require(pthread_create(&thread,NULL,held_thread,NULL)==0 && read(thread_ready[0],&token,1)==1,"added-thread-ready");
    require(kiosk_manager_recheck(&proof,&failure)!=0,"changed-real-task-census-refused");
    if(!remove)require(write(thread_release[1],"x",1)==1 && pthread_join(thread,NULL)==0,"added-thread-retired");
    require(kiosk_manager_recheck(&proof,&failure)!=0,"refused-attempt-not-retried");
    close(marker);kiosk_manager_release(&proof);
    close(thread_ready[0]);close(thread_ready[1]);close(thread_release[0]);close(thread_release[1]);
    require(loader_opened==loader_closed && owned_bus_fd==-1,"thread-bus-cleaned");
}
int main(int argc,char **argv) {
    require(argc>=2,"arguments");
    if(!strcmp(argv[1],"exec-child")) {
        require(argc==4,"exec-child-arguments");int out=atoi(argv[2]),in=atoi(argv[3]);char token;
        require(write(out,"b",1)==1 && read(in,&token,1)==1,"exec-child-barrier");close(out);close(in);return 0;
    }
    require(argc==4 && chdir(argv[2])==0,"private-workdir");
    struct stat fixture_executable;require(stat(argv[0],&fixture_executable)==0,"fixture-executable-identity");
    fixture_executable_inode=fixture_executable.st_ino;fixture_executable_device=fixture_executable.st_dev;
    unsigned baseline=descriptors();
    if(!strncmp(argv[1],"acquire-",8) || !strncmp(argv[1],"bus-",4) &&
       (!strcmp(argv[1],"bus-library") || !strcmp(argv[1],"bus-symbol") || !strcmp(argv[1],"bus-create") || !strcmp(argv[1],"bus-start"))) {
        acquire_witness(argv[1]);require(descriptors()==baseline,"acquire-fd-balance");puts("verified");return 0;
    }
    if(!strcmp(argv[1],"thread-addition") || !strcmp(argv[1],"thread-removal")) {
        thread_witness(!strcmp(argv[1],"thread-removal"));require(descriptors()==baseline,"thread-fd-balance");puts("verified");return 0;
    }
    if(!strcmp(argv[1],"same-reexec") || !strcmp(argv[1],"foreign-reexec")) {
        exec_witness(argv[0],!strcmp(argv[1],"same-reexec")?argv[0]:argv[3]);
        require(descriptors()==baseline,"exec-fd-balance");puts("verified");return 0;
    }
    struct kiosk_manager_proof p;struct kiosk_failure failure={0};setup(&p);
    int marker=open("marker",O_RDONLY|O_CLOEXEC);require(marker>=0,"expected-marker");
    require(kiosk_manager_select(&p,p.executable,marker,digest,digest,&failure)==0,"selected-native-proof");
    require(kiosk_manager_recheck(&p,&failure)==0,"original-proof-rechecked");
    const char *mode=argv[1];fault=mode;calls=0;status_calls=0;
    if(!strcmp(mode,"root"))p.root_info.st_ino++;
    if(!strcmp(mode,"mount-namespace"))p.mount_namespace.inode++;
    if(!strcmp(mode,"user-namespace"))p.user_namespace.st_ino++;
    if(!strcmp(mode,"pid-namespace"))p.pid_namespace.st_ino++;
    if(!strcmp(mode,"starttime"))p.tasks[0].start++;
    if(!strcmp(mode,"task-membership"))p.tasks[0].tid++;
    if(!strcmp(mode,"task-inode"))p.tasks[0].proc.st_ino++;
    if(!strcmp(mode,"executable"))p.executable_info.st_ino++;
    if(!strcmp(mode,"deadline"))p.deadline=kiosk_manager_now();
    if(!strcmp(mode,"pidfd-error")) {close(p.pidfd);p.pidfd=-1;}
    if(!strcmp(mode,"wrong-label"))put("label","onpc-kiosk-manager (complain)\n");
    if(!strcmp(mode,"selinux")) {p.selinux=1;put("label","system_u:system_r:onpc_kiosk_manager_t:s0\n");
        char text[256];snprintf(text,sizeof(text),"ONPC-KIOSK-VIEW\t1\tselinux\t%s\t%s\n",digest,digest);put("marker",text);
        require(controlled_fstat(marker,&p.marker_info)==0,"updated-fixture-marker");}
    if(!strcmp(mode,"adjacent-cgroup"))put("cgroup","0::/user.slice/user-1000.slice/user@1000.service-evil/init.scope\n");
    if(!strcmp(mode,"changed-cgroup"))put("cgroup","0::/user.slice/user-1000.slice/user@1000.service/other.scope\n");
    if(!strcmp(mode,"privileged-task")) {require(rename("privileged-status","status")==0,"privileged-status");}
    if(!strcmp(mode,"groups")) {p.group_count=1;p.groups[0]=777;}
    if(!strcmp(mode,"uids"))p.uid++;
    if(!strcmp(mode,"gids"))p.gid++;
    if(!strcmp(mode,"marker-replaced")) {put("replacement","foreign-marker");require(rename("replacement","marker")==0,"marker-replace");}
    if(!strcmp(mode,"material"))p.material[0]='f';
    if(!strcmp(mode,"view"))p.view[0]='f';
    if(!strcmp(mode,"boot"))p.boot[0]='x';
    int result=kiosk_manager_recheck(&p,&failure);
    int positive=!strcmp(mode,"healthy") || !strcmp(mode,"reloading") || !strcmp(mode,"selinux") || !strcmp(mode,"late-credentials");
    require((result==0)==positive,"expected-native-outcome");
    if(!strcmp(mode,"late-credentials"))require(kiosk_manager_recheck(&p,&failure)!=0,"later-census-credentials-refuse");
    if(!positive)require(failure.stage!=NULL,"closed-diagnostic");
    close(marker);kiosk_manager_release(&p);kiosk_manager_release(&p);
    require(descriptors()==baseline,"setup-fd-balance");puts("verified");return 0;
}
''')
    result = subprocess.run(
        ["cc", "-std=gnu11", "-Wall", "-Wextra", "-pthread", str(source), "-o", str(binary)],
        capture_output=True, text=True, timeout=30,
        pass_fds=test_storage.scratch_descriptors(),
    )
    assert result.returncode == 0, result.stderr
    # The development host's group-writable umask is not the selected manager
    # copy's production trust metadata. Keep the native mode guard unchanged.
    binary.chmod(0o755)
    other = directory / "other-manager"
    other.write_bytes(binary.read_bytes())
    other.chmod(0o755)
    return binary, other


@pytest.mark.parametrize("mode", [
    "healthy", "reloading", "selinux", "late-credentials", "mainpid", "invocation",
    "zero-invocation", "short-invocation", "inactive", "unit-cgroup", "bus-error",
    "wrong-type", "root", "mount-namespace", "user-namespace", "pid-namespace",
    "starttime", "task-membership", "task-inode", "executable", "deadline",
    "pidfd-error", "wrong-label", "adjacent-cgroup", "changed-cgroup", "privileged-task",
    "groups", "uids", "gids", "marker-replaced", "material", "view", "boot", "missing-task",
    "same-reexec", "foreign-reexec",
    "acquire-healthy", "acquire-zero-uid", "acquire-zero-gid", "acquire-duplicate-groups",
    "acquire-missing-task", "acquire-wrong-label", "bus-library", "bus-symbol", "bus-create", "bus-start",
    "thread-addition", "thread-removal",
    "acquire-expired-deadline", "acquire-shared-deadline",
])
def test_native_manager_proof(manager_probe, tmp_path, mode):
    binary, other = manager_probe
    result = subprocess.run(
        [str(binary), mode, str(tmp_path), str(other)],
        capture_output=True, text=True, timeout=10,
        pass_fds=test_storage.scratch_descriptors(),
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == "verified\n"
