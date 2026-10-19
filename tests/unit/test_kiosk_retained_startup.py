"""Exact PAM fresh/retained dispatch, using private real kernel mount trees.

The fresh fixture owns the preparation host-name translation. This fixture adds
only system bus/account/PAM/MAC and user-namespace platform boundaries. Manager
proc/task/starttime, pidfd, executable, mount namespace and mounted source
identities remain real. Every child has pipe barriers and is waited by its owner.
"""

import json
import hashlib
from pathlib import Path
import subprocess

import pytest

from tools import test_storage
from tests.unit import test_kiosk_fresh_startup as fresh


PLATFORM = r'''
static pid_t manager_pid;
static int manager_release=-1, manager_ready=-1, manager_pidfd=-1, gate_phase, unit_reads;
static int *clone_state;
static unsigned cleanup_failures;
static unsigned post_attach_drift, manager_acquisitions;
static int forced_elapsed;
static int independently_wrong_usr=-1;
static unsigned invocation_attached, task_scans;
static unsigned changed_start_reads, field_fault_reads, closure_checks;
static unsigned crypto_references;
static void *retained_crypto;
static void check_closure_resources(void);
static const char *fault_phase, *fault_kind;
#define clone_seen (*clone_state)
#define fault_active (clone_state[1])
#define fault_hits (clone_state[2])
#define manager_exited (clone_state[3])
static const char *pam_service="systemd-user";
static const void *pam_data[2];
static void (*pam_cleanup[2])(pam_handle_t *,void *,int);
static int bus_descriptor=-1;
struct sd_bus {int unused;};
struct sd_bus_message {const char *property;};
static struct sd_bus fixture_bus;
static struct sd_bus_message bus_request,bus_reply;
static const char *unit_cgroup="/user.slice/user-4242.slice/user@4242.service";
static void manager_command(char command) {
    char reply;
    require(write(manager_release,&command,1)==1 && read(manager_ready,&reply,1)==1 &&
        (reply==command || ((command=='f' || command=='d') && reply=='r')),"owned-manager-command");
}
static void exit_manager(void) {
    manager_command('x');struct pollfd lifetime={.fd=manager_pidfd,.events=POLLIN};
    require(poll(&lifetime,1,5000)==1 && (lifetime.revents&POLLIN),"owned-manager-exit-barrier");manager_exited=1;
}
static void activate_fault(const char *phase) {
    if(!fault_phase || strcmp(fault_phase,phase) || fault_active)return;
    fault_active=1;fault_hits++;
    if(!strcmp(fault_kind,"exit"))exit_manager();
    if(!strcmp(fault_kind,"executable"))manager_command('f');
    if(!strcmp(fault_kind,"tasks"))manager_command('t');
    if(!strcmp(fault_kind,"task-exit"))manager_command('j');
    if(!strcmp(fault_kind,"unstable-reexec")){manager_command('r');manager_command('t');}
    if(!strcmp(fault_kind,"same-reexec"))manager_command('r');
    if(!strcmp(fault_kind,"fd-reexec"))manager_command('d');
}
static int fault(const char *kind) {return fault_active && !strcmp(fault_kind,kind);}
static unsigned credential(unsigned slot,int gid,long tid) {
    char kind[16];snprintf(kind,sizeof(kind),"%s-%u",gid?"gid":"uid",slot);
    if(fault(kind) || (slot==3 && fault(gid?"gid":"uid")) ||
        (!gid && slot==1 && tid!=manager_pid && fault("worker-uid"))){field_fault_reads++;return 0;}
    return 4242;
}
static int synthetic(const char *text) {
    int fd=memfd_create("retained-platform-boundary",MFD_CLOEXEC);
    require(fd>=0 && write(fd,text,strlen(text))==(ssize_t)strlen(text) && lseek(fd,0,SEEK_SET)==0,"platform-record");return fd;
}
static ssize_t retained_getline(char **line,size_t *capacity,FILE *stream) {
    ssize_t n=getline(line,capacity,stream);if(n<=0)return n;
    char proc[64],actual[PATH_MAX],expected[64];snprintf(proc,sizeof(proc),"/proc/self/fd/%d",fileno(stream));
    snprintf(expected,sizeof(expected),"/proc/%ld/mountinfo",(long)manager_pid);
    ssize_t length=readlink(proc,actual,sizeof(actual)-1);if(length<=0)return n;actual[length]=0;
    if(strcmp(actual,expected))return n;
    /* Only translate the fixture's host-name prefix. The parser still consumes
     * the real pinned manager's procfs FD, IDs, parents, flags and full domain. */
    char *p=*line;unsigned field=0;while(field<4 && (p=strchr(p,' '))!=NULL){p++;field++;}
    char prefix[PATH_MAX];snprintf(prefix,sizeof(prefix),"%s/host",base);
    if(p && !strncmp(p,prefix,strlen(prefix)) && p[strlen(prefix)]=='/'){
        memmove(p,p+strlen(prefix),strlen(p+strlen(prefix))+1);n-=(ssize_t)strlen(prefix);}
    return n;
}
static int retained_openat(int dir,const char *path,int flags,...) {
    mode_t permission=0;if(flags&O_CREAT){va_list a;va_start(a,flags);permission=va_arg(a,int);va_end(a);}
    if(fault("boot") && !strcmp(path,"/proc/sys/kernel/random/boot_id"))return synthetic("changed-boot\n");
    if(fault("starttime") && !strcmp(path,"stat")) {
        char text[4096];int fd=openat(dir,path,flags);ssize_t n=fd<0?-1:read(fd,text,sizeof(text)-1);if(fd>=0)close(fd);
        require(n>0,"independently-read-original-task-stat");text[n]=0;
        /* Acquisition must capture the original starttime before drift. */
        if(strcmp(fault_phase,"acquire") || ++changed_start_reads>1) {
            char *part=strrchr(text,')');require(part && part[1]==' ',"real-stat-fields");part+=2;
            for(unsigned field=3;field<22;field++){part=strchr(part,' ');require(part!=NULL,"real-stat-start-field");part++;}
            require(*part>='0' && *part<='9',"real-stat-start-digit");*part=*part=='9'?'8':*part+1;field_fault_reads++;
        }
        return synthetic(text);
    }
    if(!strcmp(path,"/proc/1/uid_map") || !strcmp(path,"/proc/1/gid_map"))return synthetic("0 0 4294967295\n");
    if(!strcmp(path,"status")) {
        char text[1024],stat_text[4096];int fd=openat(dir,"stat",O_RDONLY|O_CLOEXEC);
        ssize_t n=fd<0?-1:read(fd,stat_text,sizeof(stat_text)-1);if(fd>=0)close(fd);
        if(n<=0)return -1;stat_text[n]=0;long tid=strtol(stat_text,NULL,10);
        unsigned inh=fault("cap-inh"),prm=fault("cap-prm"),eff=fault("capabilities") || fault("cap-eff") ||
            (tid!=manager_pid && fault("worker-cap")),amb=fault("cap-amb");
        if(inh || prm || eff || amb)field_fault_reads++;
        snprintf(text,sizeof(text),"Pid:\t%ld\nTgid:\t%ld\nUid:\t%u %u %u %u\nGid:\t%u %u %u %u\nGroups:\t%s\nCapInh:\t%u\nCapPrm:\t%u\nCapEff:\t%u\nCapAmb:\t%u\n",tid,(long)manager_pid,
            credential(0,0,tid),credential(1,0,tid),credential(2,0,tid),credential(3,0,tid),
            credential(0,1,tid),credential(1,1,tid),credential(2,1,tid),credential(3,1,tid),
            fault("groups")?"4242 0":"4242",inh,prm,eff,amb);
        return synthetic(text);
    }
    if(!strcmp(path,"attr/apparmor/current"))return synthetic(fault("label")?"unconfined\n":"onpc-kiosk-manager (enforce)\n");
    if(!strcmp(path,"cgroup"))return synthetic(fault("cgroup")?
        "0::/user.slice/user-4242.slice/user@4242.service-impostor/init.scope\n":fault("cgroup-drift")?
        "0::/user.slice/user-4242.slice/user@4242.service/other.scope\n":"0::/user.slice/user-4242.slice/user@4242.service/init.scope\n");
    if(!strcmp(path,"task")) {
        task_scans++;
        /* The first census pins the original real task set. Add a real task
         * before its repeated census, rather than inventing proc entries. */
        if(task_scans==2 && fault_phase && (!strcmp(fault_kind,"tasks") || !strcmp(fault_kind,"task-exit")))activate_fault("acquire");
    }
    if(!strcmp(path,"root") || !strncmp(path,"root/usr",8)) {
        if(fault("root")){char wrong[PATH_MAX];snprintf(wrong,sizeof(wrong),"%s/host/usr",base);return open(wrong,flags);}
        /* Preserve the selected task's real proc-root route into its mounts. */
        char physical[PATH_MAX];snprintf(physical,sizeof(physical),"root%s/host%s",base,path+4);
        return openat(dir,physical,flags,permission);
    }
    if(gate_phase && ((!strcmp(mode,"namespace") && clone_seen) || fault("namespace")) && !strcmp(path,"ns/mnt"))return open("/proc/self/ns/mnt",flags);
    /* Independent real namespace objects with the wrong identity. No expected
     * proof structure is edited and no host namespace is changed. */
    if((fault("userns") && !strcmp(path,"ns/user")) || (fault("pidns") && !strcmp(path,"ns/pid"))) {
        field_fault_reads++;return open("/proc/self/ns/mnt",flags);
    }
    return openat(dir,path,flags,permission);
}
static int retained_stat(const char *path,struct stat *info) {
    if(!strcmp(path,"/proc/1/ns/user"))path="/proc/self/ns/user";
    if(!strcmp(path,"/proc/1/ns/pid"))path="/proc/self/ns/pid";
    char physical[PATH_MAX];if(!strcmp(path,"/proc/1/root")){snprintf(physical,sizeof(physical),"%s/host",base);path=physical;}
    return stat(path,info);
}
static int retained_get_data(const pam_handle_t *p,const char *name,const void **out) {
    (void)p;unsigned slot=strstr(name,"transaction")!=NULL;*out=pam_data[slot];return *out?PAM_SUCCESS:PAM_NO_MODULE_DATA;
}
static int retained_set_data(pam_handle_t *p,const char *name,void *data,void (*cleanup)(pam_handle_t *,void *,int)) {
    (void)p;unsigned slot=strstr(name,"transaction")!=NULL;pam_data[slot]=data;pam_cleanup[slot]=cleanup;return PAM_SUCCESS;
}
static void retained_syslog(const pam_handle_t *p,int priority,const char *format,...) {
    (void)p;(void)priority;va_list a;va_start(a,format);vfprintf(stderr,format,a);fputc('\n',stderr);va_end(a);
}
static int retained_item(const pam_handle_t *p,int item,const void **value) {
    (void)p;require(item==PAM_SERVICE,"PAM-service-item");*value=pam_service;return PAM_SUCCESS;
}
static int retained_profile(const char *name) {
    require(!strcmp(name,gate_phase?"onpc-kiosk-gate":"onpc-kiosk-manager"),"role-final-profile");mac_calls++;
    if(gate_phase) {
        /* The preparation lock remains owned until MAC returns. Everything
         * else is either an exact borrowed FD or that one owned lock. */
        require(descriptors()==(unsigned)final_fd_baseline+1,"setup-FDs-closed-before-final-MAC");
        char lock_path[PATH_MAX];struct stat lock_info;unsigned owned_locks=0;
        snprintf(lock_path,sizeof(lock_path),"%s/lock",base);require(lstat(lock_path,&lock_info)==0,"independent-final-lock-inode");
        for(int fd=0;fd<4096;fd++) {
            struct stat current;int exists=fstat(fd,&current)==0;
            if(caller_fds[fd])require(exists && current.st_dev==caller_objects[fd].st_dev &&
                current.st_ino==caller_objects[fd].st_ino && current.st_mode==caller_objects[fd].st_mode,"borrowed-FD-identities-before-retained-MAC");
            else if(exists){require(current.st_dev==lock_info.st_dev && current.st_ino==lock_info.st_ino,"only-owned-preparation-lock-survives-before-MAC");owned_locks++;}
        }
        require(owned_locks==1,"one-owned-preparation-lock-before-MAC");
        if(!strcmp(mode,"exit-after-decision"))exit_manager();
    }
    return 0;
}
static int retained_get_profile(char **label,char **enforce) {
    const char *name=gate_phase?"onpc-kiosk-gate":"onpc-kiosk-manager";
    *label=calloc(1,64);strcpy(*label,name);*enforce=*label+40;strcpy(*enforce,"enforce");return 1;
}
static int bus_new(struct sd_bus **out){bus_descriptor=open("/dev/null",O_RDONLY|O_CLOEXEC);*out=&fixture_bus;return bus_descriptor<0?-1:0;}
static int bus_address(struct sd_bus *b,const char *p){(void)b;require(!strcmp(p,"unix:path=/run/dbus/system_bus_socket"),"system-bus-route");return 0;}
static int bus_client(struct sd_bus *b,int c){(void)b;return c==1?0:-1;}
static int bus_start(struct sd_bus *b){(void)b;return 0;}
static int bus_fd(struct sd_bus *b){(void)b;return bus_descriptor;}
static struct sd_bus *bus_unref(struct sd_bus *b){(void)b;if(bus_descriptor>=0)close(bus_descriptor);bus_descriptor=-1;return NULL;}
static int bus_new_call(struct sd_bus *b,struct sd_bus_message **out,const char *dest,const char *path,const char *interface,const char *method){
    (void)b;require(!strcmp(dest,"org.freedesktop.systemd1") && !strcmp(path,"/org/freedesktop/systemd1/unit/user_404242_2eservice") &&
        !strcmp(interface,"org.freedesktop.DBus.Properties") && !strcmp(method,"Get"),"exact-manager-unit");*out=&bus_request;return 0;}
static int bus_append(struct sd_bus_message *m,const char *signature,...){
    va_list a;va_start(a,signature);(void)va_arg(a,const char *);m->property=va_arg(a,const char *);va_end(a);return !strcmp(signature,"ss")?1:-1;}
static int bus_call(struct sd_bus *b,struct sd_bus_message *m,uint64_t timeout,void *error,struct sd_bus_message **out){
    (void)b;(void)error;require(timeout>0 && timeout<=5000000,"bounded-manager-query");bus_reply.property=m->property;*out=&bus_reply;return 1;}
static int bus_enter(struct sd_bus_message *m,char type,const char *contents){(void)m;(void)contents;return type=='v'?1:-1;}
static int bus_end(struct sd_bus_message *m,int complete){(void)m;(void)complete;return 1;}
static int bus_leave(struct sd_bus_message *m){(void)m;return 1;}
static struct sd_bus_message *bus_message_unref(struct sd_bus_message *m){(void)m;return NULL;}
static int bus_read(struct sd_bus_message *m,const char *signature,...){
    va_list a;va_start(a,signature);void *out=va_arg(a,void *);va_end(a);
    if(!strcmp(signature,"u")){unit_reads++;*(uint32_t *)out=manager_pid+((clone_seen && !strcmp(mode,"manager")) || fault("mainpid"));}
    else if(!strcmp(m->property,"ActiveState"))*(const char **)out=!strcmp(mode,"inactive")?"inactive":"active";
    else *(const char **)out=fault("unit-cgroup")?"/different-unit":unit_cgroup;return 1;}
static int bus_array(struct sd_bus_message *m,char type,const void **out,size_t *size){
    (void)m;require(type=='y',"invocation-id-type");static unsigned char bytes[16];memset(bytes,0,16);
    bytes[0]=(clone_seen && !strcmp(mode,"invocation")) || fault("invocation")?2:1;*out=bytes;*size=16;return 1;}
static void *retained_dlopen(const char *path,int flags){
    void *library=!strcmp(path,"libsystemd.so.0")?(void *)4:fixture_dlopen(path,flags);
    if(gate_phase && library && !strcmp(path,"libcrypto.so.3")){retained_crypto=library;crypto_references++;}return library;}
static void *retained_dlsym(void *library,const char *name){
    if(library==(void *)1){if(!strcmp(name,"aa_change_profile"))return (void *)retained_profile;if(!strcmp(name,"aa_getcon"))return (void *)retained_get_profile;}
    if(library!=(void *)4)return fixture_dlsym(library,name);
#define BUS_SYMBOL(n,f) if(!strcmp(name,n))return (void *)f
    BUS_SYMBOL("sd_bus_new",bus_new);BUS_SYMBOL("sd_bus_set_address",bus_address);BUS_SYMBOL("sd_bus_set_bus_client",bus_client);
    BUS_SYMBOL("sd_bus_start",bus_start);BUS_SYMBOL("sd_bus_get_fd",bus_fd);BUS_SYMBOL("sd_bus_unref",bus_unref);
    BUS_SYMBOL("sd_bus_message_new_method_call",bus_new_call);BUS_SYMBOL("sd_bus_message_append",bus_append);BUS_SYMBOL("sd_bus_call",bus_call);
    BUS_SYMBOL("sd_bus_message_enter_container",bus_enter);BUS_SYMBOL("sd_bus_message_exit_container",bus_leave);
    BUS_SYMBOL("sd_bus_message_read",bus_read);BUS_SYMBOL("sd_bus_message_read_array",bus_array);BUS_SYMBOL("sd_bus_message_at_end",bus_end);
    BUS_SYMBOL("sd_bus_message_unref",bus_message_unref);
#undef BUS_SYMBOL
    return NULL;
}
static int retained_dlclose(void *library){
    if(gate_phase && library==retained_crypto){
        require(crypto_references>0,"owned-crypto-reference-close");crypto_references--;
        /* Host/account/policy proofs hold their own references to this same
         * loader object. Only the last reference is the end of setup closure. */
        if(!crypto_references && fault_phase && !strcmp(fault_phase,"closure")){
            check_closure_resources();closure_checks++;activate_fault("closure");}
    }
    return library==(void *)4?0:fixture_dlclose(library);}
static int retained_open_tree(int dir,const char *path,unsigned flags) {
    int result=-1;
    if(gate_phase && (flags&OPEN_TREE_CLONE) && !clone_seen) {
        if(!strcmp(mode,"missing-nested-clone"))flags&=~AT_RECURSIVE;
        if(!strcmp(mode,"wrong-clone")) {
            /* The clone worker has already entered the manager namespace.
             * Return a real foreign detached clone created before entry:
             * names select the manager view, and cloning another namespace's
             * attached mount through an FD refuses with EINVAL on Linux. */
            struct stat selected,wrong;
            require(independently_wrong_usr>=0 && fstat(dir,&selected)==0 &&
                fstat(independently_wrong_usr,&wrong)==0 &&
                (selected.st_dev!=wrong.st_dev || selected.st_ino!=wrong.st_ino),"independently-wrong-clone-root-inode");
            result=fcntl(independently_wrong_usr,F_DUPFD_CLOEXEC,3);
            require(result>=0,"real-foreign-detached-clone-transfer");
        }
    }
    if(result<0)result=open_tree(dir,path,flags);
    if(gate_phase && result>=0 && (flags&OPEN_TREE_CLONE)) {
        clone_seen++;
        if(clone_seen==1 && !strcmp(mode,"same-reexec"))manager_command('r');
        if(clone_seen==1 && !strcmp(mode,"same-fd-reexec"))manager_command('d');
        if(clone_seen==1 && !strcmp(mode,"foreign-reexec"))manager_command('f');
        if(clone_seen==1)activate_fault("clone");
        if(clone_seen==1 && !strcmp(mode,"exit-after-clone")) {
            manager_command('x');struct pollfd lifetime={.fd=manager_pidfd,.events=POLLIN};
            require(poll(&lifetime,1,5000)==1 && (lifetime.revents&POLLIN),"owned-manager-exit-observed-before-final-proof");
            int copy=openat(result,"bin/native",O_RDONLY|O_CLOEXEC),nested=openat(result,"bin/ambient-tree/nested/leaf",O_RDONLY|O_CLOEXEC);
            char magic[4],bytes[14]={0};
            require(copy>=0 && nested>=0 && read(copy,magic,4)==4 && !memcmp(magic,"\177ELF",4) &&
                read(nested,bytes,sizeof(bytes))==13 && !strcmp(bytes,"nested-source") && close(copy)==0 && close(nested)==0,
                "independent-recursive-clone-still-readable-after-manager-exit");
        }
    }
    return result;
}
static int retained_move_mount(int from,const char *source,int to,const char *target,unsigned flags) {
    int result=move_mount(from,source,to,target,flags);
    if(gate_phase && !result) {
        char proc[64],actual[PATH_MAX],expected[PATH_MAX];snprintf(proc,sizeof(proc),"/proc/self/fd/%d",to);
        ssize_t n=readlink(proc,actual,sizeof(actual)-1);if(n>0){actual[n]=0;snprintf(expected,sizeof(expected),"%s/host/usr",base);
            if(!strcmp(actual,expected)){invocation_attached++;activate_fault("final");}}
    }
    if(gate_phase && !result && !strcmp(mode,"post-attach-required-drift")) {
        char proc[64],actual[PATH_MAX],expected[PATH_MAX];snprintf(proc,sizeof(proc),"/proc/self/fd/%d",to);
        ssize_t n=readlink(proc,actual,sizeof(actual)-1);if(n>0){actual[n]=0;snprintf(expected,sizeof(expected),"%s/host/usr",base);
            if(!strcmp(actual,expected)){require(pwrite(original_source,"X",1,100)==1 && fsync(original_source)==0,"original-host-drift-after-private-attachment");post_attach_drift++;}}
    }
    return result;
}
static int retained_mount(const char *source,const char *target,const char *type,unsigned long flags,const void *data) {
    int result=fixture_mount(source,target,type,flags,data);
    if(gate_phase && result) {
        int saved=errno;char from[PATH_MAX]={0},to[PATH_MAX]={0};
        ssize_t a=source?readlink(source,from,sizeof(from)-1):-1,b=target?readlink(target,to,sizeof(to)-1):-1;
        if(a>=0)from[a]=0;if(b>=0)to[b]=0;
        fprintf(stderr,"retained-mount-failure source=%s target=%s flags=%lu errno=%d source-name=%s target-name=%s\n",
            source?source:"-",target?target:"-",flags,saved,from,to);errno=saved;
    }
    return result;
}
static int retained_umount(const char *path,int flags) {
    if(gate_phase && !strcmp(mode,"cleanup-failure") && !cleanup_failures++){errno=EBUSY;return -1;}
    return fixture_umount(path,flags);
}
static int retained_clock_gettime(clockid_t clock,struct timespec *time) {
    int result=clock_gettime(clock,time);
    if(!result && gate_phase && ((!strcmp(mode,"deadline") && clone_seen) || forced_elapsed))time->tv_sec+=61;
    return result;
}
static int retained_poll(struct pollfd *fds,nfds_t count,int milliseconds) {
    if(gate_phase && !strcmp(mode,"helper-timeout") && milliseconds>1000 && !forced_elapsed) {
        /* One bounded wait advances the fixture's monotonic clock beyond the
         * already chosen deadline. The production budget is never renewed. */
        char witness[PATH_MAX];snprintf(witness,sizeof(witness),"%s/timeout-waiting",base);
        for(unsigned i=0;i<50;i++) {
            int result=poll(fds,count,100);if(result)return result;
            if(access(witness,F_OK)==0){forced_elapsed=1;return 0;}
        }
        require(0,"helper-reached-owned-timeout-barrier");return -1;
    }
    return poll(fds,count,milliseconds);
}
static long retained_syscall(long number,...) {
    va_list a;va_start(a,number);long result;
    if(number==SYS_statx){int fd=va_arg(a,int);const char *path=va_arg(a,const char *);int flags=va_arg(a,int);unsigned mask=va_arg(a,unsigned);struct statx *info=va_arg(a,struct statx *);result=syscall(number,fd,path,flags,mask,info);
    }else if(number==SYS_clone3){void *args=va_arg(a,void *);size_t size=va_arg(a,size_t);result=syscall(number,args,size);
    }else if(number==SYS_pidfd_send_signal){int pidfd=va_arg(a,int),signal_number=va_arg(a,int);void *info=va_arg(a,void *);unsigned flags=va_arg(a,unsigned);result=syscall(number,pidfd,signal_number,info,flags);
    }else if(number==SYS_move_mount){int from=va_arg(a,int);const char *source=va_arg(a,const char *);int to=va_arg(a,int);const char *target=va_arg(a,const char *);unsigned flags=va_arg(a,unsigned);result=syscall(number,from,source,to,target,flags);
    }else if(number==SYS_mount_setattr){int fd=va_arg(a,int);const char *path=va_arg(a,const char *);unsigned flags=va_arg(a,unsigned);void *attr=va_arg(a,void *);size_t size=va_arg(a,size_t);result=syscall(number,fd,path,flags,attr,size);
    }else if(number==SYS_pidfd_open){int pid=va_arg(a,int);unsigned flags=va_arg(a,unsigned);
        if(gate_phase){manager_acquisitions++;require(pid==manager_pid && manager_acquisitions==1,"one-original-manager-no-replacement-acquisition");
            if(!fault_kind || (strcmp(fault_kind,"tasks") && strcmp(fault_kind,"task-exit")))activate_fault("acquire");}
        result=syscall(number,pid,flags);
    }else if(number==SYS_close_range){unsigned first=va_arg(a,unsigned),last=va_arg(a,unsigned),flags=va_arg(a,unsigned);result=syscall(number,first,last,flags);
    }else {fprintf(stderr,"unsupported-fixture-syscall:%ld\n",number);errno=ENOSYS;result=-1;}
    va_end(a);return result;
}
'''


MAIN = r'''
static void check_closure_resources(void) {
    struct kiosk_admission_transaction *owner=(void *)pam_data[1];require(owner!=NULL,"closure-PAM-owner");
    struct kiosk_retained_startup *gate=&owner->retained;struct kiosk_fresh_startup *s=&gate->common;
    require(s->stage && !strcmp(s->stage,"closure") && s->runtime<0 && s->skeleton<0 && s->target_parent<0 &&
        s->marker<0 && s->view.root<0 && s->realized.root<0 && s->host.roots.root<0 && s->account.roots.root<0 &&
        s->roots.root<0 && s->roots.usr<0 && gate->source.fd<0 && gate->mountinfo<0 && gate->marker<0 &&
        gate->invocation<0 && gate->manager.acquired && gate->manager.selected && gate->manager.proc>=0 && gate->manager.pidfd>=0,
        "independent-setup-closed-original-manager-still-owned-before-last-check");
}
struct tree_witness {char path[PATH_MAX];struct stat info;uint64_t hash;};
static struct tree_witness manager_before[64],records_before[64];
static unsigned manager_count,record_count;
struct manager_identity {struct stat objects[8];char start[32];pid_t tids[8];unsigned count;};
static void identity_snapshot(int proc,struct manager_identity *identity) {
    char root[PATH_MAX],usr[PATH_MAX];snprintf(root,sizeof(root),"root%s/host",base);snprintf(usr,sizeof(usr),"root%s/host/usr",base);
    const char *paths[]={".","root",root,usr,"exe","ns/mnt","ns/user","ns/pid"};
    for(unsigned i=0;i<8;i++)require(fstatat(proc,paths[i],&identity->objects[i],0)==0,"independent-manager-object-snapshot");
    int fd=openat(proc,"stat",O_RDONLY|O_CLOEXEC);char text[4096];ssize_t n=fd<0?-1:read(fd,text,sizeof(text)-1);
    require(n>0 && close(fd)==0,"independent-manager-starttime-read");text[n]=0;
    char *end=strrchr(text,')'),*save=NULL;require(end!=NULL,"independent-manager-stat-syntax");
    char *word=strtok_r(end+1," ",&save);
    for(unsigned field=3;field<22;field++){require(word!=NULL,"independent-manager-stat-complete");word=strtok_r(NULL," ",&save);}
    require(word && strlen(word)<sizeof(identity->start),"independent-manager-starttime");strcpy(identity->start,word);
    fd=openat(proc,"task",O_RDONLY|O_DIRECTORY|O_CLOEXEC);DIR *tasks=fd<0?NULL:fdopendir(fd);
    require(tasks!=NULL,"independent-task-set");struct dirent *entry;identity->count=0;
    while((entry=readdir(tasks)))if(strcmp(entry->d_name,".") && strcmp(entry->d_name,"..")){
        require(identity->count<8,"finite-independent-tasks");identity->tids[identity->count++]=(pid_t)strtol(entry->d_name,NULL,10);}
    closedir(tasks);
    for(unsigned i=0;i<identity->count;i++)for(unsigned j=i+1;j<identity->count;j++)if(identity->tids[j]<identity->tids[i]){
        pid_t swap=identity->tids[i];identity->tids[i]=identity->tids[j];identity->tids[j]=swap;}
}
static void identity_unchanged(const struct manager_identity *before,const struct manager_identity *after) {
    require(!strcmp(before->start,after->start) && before->count==after->count &&
        !memcmp(before->tids,after->tids,before->count*sizeof(pid_t)),"independent-original-leader-and-task-lifetimes");
    for(unsigned i=0;i<8;i++)require(before->objects[i].st_dev==after->objects[i].st_dev &&
        before->objects[i].st_ino==after->objects[i].st_ino && before->objects[i].st_mode==after->objects[i].st_mode,
        "independent-original-proc-root-source-executable-and-namespaces");
}
static uint64_t independent_hash(int fd) {
    uint64_t hash=1469598103934665603ULL;char bytes[8192];ssize_t n;
    while((n=read(fd,bytes,sizeof(bytes)))>0)for(ssize_t i=0;i<n;i++){hash^=(unsigned char)bytes[i];hash*=1099511628211ULL;}
    require(n==0,"independent-complete-source-read");return hash;
}
static void observe_tree(int root,const char *name,struct tree_witness *rows,unsigned *count,int checking) {
    require(*count<64,"finite-independent-tree");struct stat info;require(fstatat(root,name,&info,AT_SYMLINK_NOFOLLOW)==0,"independent-tree-entry");
    struct tree_witness *row=rows+(*count)++;uint64_t hash=0;
    if(S_ISREG(info.st_mode)){int fd=openat(root,name,O_RDONLY|O_CLOEXEC|O_NOFOLLOW);require(fd>=0,"independent-source-open");hash=independent_hash(fd);close(fd);}
    else require(S_ISDIR(info.st_mode),"independent-closed-tree-kind");
    if(checking)require(!strcmp(row->path,name) && row->info.st_dev==info.st_dev && row->info.st_ino==info.st_ino &&
        row->info.st_mode==info.st_mode && row->info.st_uid==info.st_uid && row->info.st_gid==info.st_gid &&
        row->info.st_size==info.st_size && row->info.st_mtim.tv_sec==info.st_mtim.tv_sec && row->info.st_mtim.tv_nsec==info.st_mtim.tv_nsec &&
        row->info.st_ctim.tv_sec==info.st_ctim.tv_sec && row->info.st_ctim.tv_nsec==info.st_ctim.tv_nsec && row->hash==hash,"unchanged-manager-source-dentry-record-bytes");
    else {strcpy(row->path,name);row->info=info;row->hash=hash;}
    if(!S_ISDIR(info.st_mode))return;
    int fd=openat(root,name,O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC);require(fd>=0,"independent-tree-directory");
    struct dirent **names=NULL;int n=scandirat(fd,".",&names,NULL,alphasort);require(n>=0,"independent-complete-tree-enumeration");
    for(int i=0;i<n;i++){if(strcmp(names[i]->d_name,".") && strcmp(names[i]->d_name,"..")){
        char path[PATH_MAX];require(snprintf(path,sizeof(path),"%s/%s",name,names[i]->d_name)<PATH_MAX,"independent-tree-path");observe_tree(root,path,rows,count,checking);}free(names[i]);}
    free(names);close(fd);
}
static void put_text(const char *name,const char *text) {
    char path[PATH_MAX];snprintf(path,sizeof(path),"%s/%s",base,name);int fd=open(path,O_WRONLY|O_CREAT|O_TRUNC|O_CLOEXEC,0600);
    require(fd>=0 && write(fd,text,strlen(text))==(ssize_t)strlen(text) && close(fd)==0,"owned-scene-record");
}
static void release_pam(void) {for(int slot=1;slot>=0;slot--)if(pam_data[slot]){pam_cleanup[slot](NULL,(void *)pam_data[slot],PAM_SUCCESS);pam_data[slot]=NULL;}}
static const char *expected_stage(const char *name) {
    if(!strcmp(name,"healthy") || !strcmp(name,"ambient-narrow") || !strcmp(name,"same-reexec") ||
        !strcmp(name,"same-fd-reexec") || !strcmp(name,"exit-after-decision") ||
        !strcmp(name,"stable-two-tasks") || !strcmp(name,"capabilities-inherited") || !strcmp(name,"capabilities-zero"))return "armed";
    if(!strncmp(name,"capabilities-",13))return "final-lock";
    if(fault_phase) {
        if(!strcmp(fault_kind,"same-reexec") || !strcmp(fault_kind,"fd-reexec"))return "armed";
        if(!strcmp(fault_phase,"closure"))return "closure";
        if(!strcmp(fault_phase,"final"))return "final-source";
        if(!strcmp(fault_phase,"clone"))return "source-clone";
        return !strcmp(fault_kind,"executable")?"completed-record":"manager";
    }
    if(!strcmp(name,"required-drift") || strstr(name,"ready") || strstr(name,"source"))return "completed-record";
    if(!strcmp(name,"post-attach-required-drift"))return "final-host";
    if(!strcmp(name,"inactive"))return "manager";
    if(!strcmp(name,"helper-exit") || !strcmp(name,"helper-timeout"))return "measurement";
    if(!strcmp(name,"result-malformed"))return "retained-plan";
    if(!strcmp(name,"cleanup-failure"))return "staging";
    return "source-clone";
}
static int task_release[2],task_ready[2];
static pthread_t extra_task;
static void *held_task(void *unused) {
    (void)unused;char token='t';require(write(task_ready[1],&token,1)==1 &&
        read(task_release[0],&token,1)==1,"owned-extra-task-barriers");return NULL;
}
static void manager_loop(int out,int in,int reexecuted) {
    int task_live=0;
    char token=reexecuted?'r':'a';require(write(out,&token,1)==1,"manager-ready-barrier");
    while(read(in,&token,1)==1) {
        if(token=='r' || token=='f' || token=='d') {
            char path[PATH_MAX],a[32],b[32];snprintf(path,sizeof(path),"%s/%s",base,token=='r'?"host/usr/bin/native":"other-manager");
            if(token=='d')snprintf(path,sizeof(path),"%s/host/usr/bin/native",base);
            snprintf(a,sizeof(a),"%d",out);snprintf(b,sizeof(b),"%d",in);
            if(token=='d') {
                int fd=open(path,O_RDONLY|O_CLOEXEC);require(fd>=0,"pinned-same-manager-exec-FD");
                char *arguments[]={path,"manager-loop",(char *)base,a,b,NULL};extern char **environ;
                fexecve(fd,arguments,environ);_exit(127);
            }
            execl(path,path,"manager-loop",base,a,b,NULL);_exit(127);
        }
        if(token=='t') {
            require(!task_live && pipe(task_release)==0 && pipe(task_ready)==0 &&
                pthread_create(&extra_task,NULL,held_task,NULL)==0,"owned-extra-task-created");
            require(read(task_ready[0],&token,1)==1 && token=='t' && write(out,&token,1)==1,"real-extra-task-stable-before-proof");task_live=1;continue;
        }
        if(token=='j') {
            require(task_live && write(task_release[1],"x",1)==1 && pthread_join(extra_task,NULL)==0,"original-extra-task-retired-before-proof");
            close(task_release[0]);close(task_release[1]);close(task_ready[0]);close(task_ready[1]);task_live=0;
            require(write(out,"j",1)==1,"original-extra-task-exit-acknowledged");continue;
        }
        require(token=='x',"finite-manager-command");require(write(out,&token,1)==1,"manager-exit-barrier");break;
    }
    if(task_live) {
        require(write(task_release[1],"x",1)==1 && pthread_join(extra_task,NULL)==0,"owned-extra-task-joined");
        close(task_release[0]);close(task_release[1]);close(task_ready[0]);close(task_ready[1]);
    }
}
static void actual_nested(void) {
    char path[PATH_MAX],parent[PATH_MAX],text[32]={0};struct statx a,b;
    require(actual_walk("/usr")==(!strcmp(mode,"ambient-narrow")?13U:14U),"independent-closed-actual-tree-domain");
    snprintf(path,sizeof(path),"%s/host/usr/bin/ambient-tree/nested/leaf",base);
    int fd=open(path,O_RDONLY|O_CLOEXEC);require(fd>=0 && read(fd,text,sizeof(text))==13 && !strcmp(text,"nested-source"),"independent-recursive-bytes");close(fd);
    require(open(path,O_WRONLY|O_CLOEXEC)<0 && errno==EROFS,"independent-nested-mount-readonly");
    snprintf(path,sizeof(path),"%s/host/usr/bin/ambient-tree/nested",base);snprintf(parent,sizeof(parent),"%s/host/usr/bin/ambient-tree",base);
    require(statx(AT_FDCWD,path,AT_SYMLINK_NOFOLLOW,STATX_MNT_ID,&a)==0 && statx(AT_FDCWD,parent,AT_SYMLINK_NOFOLLOW,STATX_MNT_ID,&b)==0 && a.stx_mnt_id!=b.stx_mnt_id,"independent-recursive-submount");
    snprintf(path,sizeof(path),"%s/host/usr/forbidden-write",base);require(mkdir(path,0755)!=0 && errno==EROFS,"independent-private-readonly");
}
int main(int argc,char **argv) {
    if(argc==5 && !strcmp(argv[1],"manager-loop")){base=argv[2];manager_loop(atoi(argv[3]),atoi(argv[4]),1);return 0;}
    require(argc==3,"arguments");base=argv[2];mode="healthy";namespaces();
    clone_state=mmap(NULL,4*sizeof(*clone_state),PROT_READ|PROT_WRITE,MAP_SHARED|MAP_ANONYMOUS,-1,0);require(clone_state!=MAP_FAILED,"shared-clone-barrier");
    char path[PATH_MAX];snprintf(path,sizeof(path),"%s/host/usr/bin/ambient-tree/nested",base);
    require(mount("tmpfs",path,"tmpfs",0,"size=1m,mode=0755")==0,"private-recursive-source");
    snprintf(path,sizeof(path),"%s/host/usr/bin/ambient-tree/nested/leaf",base);
    int fd=open(path,O_WRONLY|O_CREAT|O_CLOEXEC,0644);require(fd>=0 && write(fd,"nested-source",13)==13 && fchmod(fd,0644)==0 && close(fd)==0,"nested-source-bytes");
    snprintf(path,sizeof(path),"%s/host/usr/bin/native",base);original_source=open(path,O_RDWR|O_CLOEXEC);char original_required_byte;
    require(original_source>=0 && pread(original_source,&original_required_byte,1,100)==1,"original-host-required-fd-and-byte");
    snprintf(path,sizeof(path),"%s/host/usr",base);require(lstat(path,&original_target_info)==0,"original-host-root");
    int ready[2],release[2];require(pipe(ready)==0 && pipe(release)==0,"manager-owned-pipes");manager_pid=fork();require(manager_pid>=0,"manager-owned-fork");
    if(!manager_pid) {
        close(ready[0]);close(release[1]);int result=kiosk_confinement(NULL);
        require(result==PAM_SUCCESS,"exact-production-fresh-caller");release_pam();actual_nested();
        char executable[PATH_MAX],a[32],b[32];snprintf(executable,sizeof(executable),"%s/host/usr/bin/native",base);
        snprintf(a,sizeof(a),"%d",ready[1]);snprintf(b,sizeof(b),"%d",release[0]);
        execl(executable,executable,"manager-loop",base,a,b,NULL);_exit(127);
    }
    close(ready[1]);close(release[0]);manager_ready=ready[0];manager_release=release[1];char token;
    require(read(manager_ready,&token,1)==1 && token=='r',"manager-fresh-and-exec-complete");
    manager_pidfd=syscall(SYS_pidfd_open,manager_pid,0);require(manager_pidfd>=0,"independent-owned-manager-pidfd");
    snprintf(path,sizeof(path),"/proc/%ld/ns/mnt",(long)manager_pid);
    int held_manager_namespace=open(path,O_RDONLY|O_CLOEXEC);require(held_manager_namespace>=0,"independent-manager-namespace-lifetime");
    mode=argv[1];gate_phase=1;pam_service="gdm-password";put_text("mode",mode);
    if(capability_model())capability_begin();
    const char *phases[]={"acquire","clone","final","closure"};
    for(unsigned i=0;i<4;i++)if(!strncmp(mode,phases[i],strlen(phases[i])) && mode[strlen(phases[i])]=='-'){
        fault_phase=phases[i];fault_kind=mode+strlen(phases[i])+1;
    }
    if(!strcmp(mode,"stable-two-tasks") || (fault_kind && (!strcmp(fault_kind,"task-exit") || !strncmp(fault_kind,"worker-",7))))manager_command('t');
    snprintf(path,sizeof(path),"/proc/%ld",(long)manager_pid);int independent_proc=open(path,O_PATH|O_DIRECTORY|O_CLOEXEC);
    require(independent_proc>=0,"independent-original-manager-proc");struct manager_identity identity_before,identity_after;
    identity_snapshot(independent_proc,&identity_before);
    require(identity_before.count==((!strcmp(mode,"stable-two-tasks") || (fault_kind &&
        (!strcmp(fault_kind,"task-exit") || !strncmp(fault_kind,"worker-",7))))?2U:1U),"independent-original-task-count");
    snprintf(path,sizeof(path),"%s/host/usr/bin/ambient",base);
    if(!strcmp(mode,"ambient-narrow"))require(chmod(path,0666)==0,"host-ambient-narrowing");
    if(!strcmp(mode,"required-drift"))require(pwrite(original_source,"X",1,100)==1 && fsync(original_source)==0,"host-required-drift");
    if(!strcmp(mode,"absent-ready") || !strcmp(mode,"stale-ready") || !strcmp(mode,"forged-ready") || !strcmp(mode,"missing-source") || !strcmp(mode,"foreign-source")) {
        char runtime[PATH_MAX];snprintf(runtime,sizeof(runtime),"%s/runtime",base);DIR *d=opendir(runtime);require(d!=NULL,"completed-generation-list");struct dirent *e;char selected[65]={0};
        while((e=readdir(d)))if(strlen(e->d_name)==64){require(!*selected,"single-manager-record");strcpy(selected,e->d_name);}closedir(d);require(*selected,"completed-manager-record");
        snprintf(path,sizeof(path),"%s/runtime/%s/%s",base,selected,strstr(mode,"source")?"native-0":"ready");
        if(!strcmp(mode,"absent-ready") || !strcmp(mode,"missing-source"))require(unlink(path)==0,"owned-record-removal-fault");
        else if(!strcmp(mode,"foreign-source")) {
            char foreign[PATH_MAX];snprintf(foreign,sizeof(foreign),"%s/foreign-native",base);
            int original=open(path,O_RDONLY|O_CLOEXEC),replacement=open(foreign,O_WRONLY|O_CREAT|O_EXCL|O_CLOEXEC,0755);
            require(original>=0 && replacement>=0,"foreign-copy-fault-descriptors");char bytes[8192];ssize_t n;
            while((n=read(original,bytes,sizeof(bytes)))>0)require(write(replacement,bytes,(size_t)n)==n,"foreign-copy-fault-bytes");
            require(n==0 && fchmod(replacement,0755)==0 && close(original)==0 && close(replacement)==0 && rename(foreign,path)==0,"same-byte-foreign-copy-inode-fault");
        }else {
            int fault=open(path,O_RDWR|O_CLOEXEC);char bytes[1024];ssize_t n=fault<0?-1:pread(fault,bytes,sizeof(bytes),0);
            require(n>0,"owned-ready-fault-read");unsigned field=!strcmp(mode,"stale-ready")?5:4;char *p=bytes;
            for(unsigned i=0;i<field;i++){p=memchr(p,'\t',(size_t)(bytes+n-p));require(p!=NULL,"canonical-ready-fault-field");p++;}
            *p=*p=='0'?'1':'0';require(pwrite(fault,p,1,p-bytes)==1 && fsync(fault)==0 && close(fault)==0,"syntactically-valid-stale-or-forged-ready-fault");
        }
    }
    char manager_path[PATH_MAX],runtime_path[PATH_MAX];snprintf(manager_path,sizeof(manager_path),"/proc/%ld/root%s/host/usr",(long)manager_pid,base);
    snprintf(runtime_path,sizeof(runtime_path),"%s/runtime",base);
    int held_manager=open(manager_path,O_RDONLY|O_DIRECTORY|O_CLOEXEC),held_records=open(runtime_path,O_RDONLY|O_DIRECTORY|O_CLOEXEC);
    require(held_manager>=0 && held_records>=0,"independently-held-manager-and-record-roots");
    if(!strcmp(mode,"wrong-clone")) {
        snprintf(path,sizeof(path),"%s/host/usr",base);int wrong_host=open(path,O_PATH|O_DIRECTORY|O_CLOEXEC);
        require(wrong_host>=0,"wrong-host-source-pinned-before-namespace-entry");
        independently_wrong_usr=open_tree(wrong_host,"",OPEN_TREE_CLONE|AT_RECURSIVE|AT_EMPTY_PATH|OPEN_TREE_CLOEXEC);
        struct stat selected,wrong;
        struct statx original_mount,clone_mount;
        require(independently_wrong_usr>=0 && fstat(held_manager,&selected)==0 &&
            fstat(independently_wrong_usr,&wrong)==0 &&
            (selected.st_dev!=wrong.st_dev || selected.st_ino!=wrong.st_ino) &&
            statx(wrong_host,"",AT_EMPTY_PATH,STATX_MNT_ID,&original_mount)==0 &&
            statx(independently_wrong_usr,"",AT_EMPTY_PATH,STATX_MNT_ID,&clone_mount)==0 &&
            original_mount.stx_mnt_id!=clone_mount.stx_mnt_id && close(wrong_host)==0,
            "real-wrong-detached-clone-before-namespace-entry");
    }
    observe_tree(held_manager,".",manager_before,&manager_count,0);observe_tree(held_records,".",records_before,&record_count,0);
    require(kiosk_admission(NULL,"oh-no-parent-control-kiosk")==PAM_SUCCESS,"owned-gate-admission");unsigned baseline=descriptors();
    final_fd_baseline=(int)baseline;
    for(int caller=0;caller<4096;caller++)caller_fds[caller]=fstat(caller,&caller_objects[caller])==0;
    int result=kiosk_confinement(NULL);int positive=!strcmp(expected_stage(mode),"armed");
    if(capability_model())capability_expect(result==PAM_SUCCESS?0:-1);
    if(positive)require(capability_get_calls==2 && capability_set_calls==1 && capability_ambient_calls==1,
        "production-retained-cut-uses-shared-capability-clear");
    if((result==PAM_SUCCESS)!=positive)fprintf(stderr,"retained-result:%s:%d clone=%d unit-reads=%d\n",mode,result,clone_seen,unit_reads);
    require((result==PAM_SUCCESS)==positive,"exact-production-retained-caller-result");
    struct kiosk_admission_transaction *owner=(void *)pam_data[1];require(owner!=NULL,"retained-PAM-transaction-owner");
    struct kiosk_fresh_startup *transaction=&owner->retained.common;
    if(!transaction->stage || strcmp(transaction->stage,expected_stage(mode)))fprintf(stderr,"retained-boundary mode=%s expected=%s actual=%s\n",mode,expected_stage(mode),transaction->stage?transaction->stage:"-");
    require(transaction->stage && !strcmp(transaction->stage,expected_stage(mode)),"exact-fault-applicability-boundary");
    require(transaction->child.started && transaction->child.reaped && transaction->child.pidfd<0 && transaction->child.channel<0 &&
        transaction->closed && owner->closed && transaction->armed==positive,"helper-reaped-transaction-closed-and-arm-state");
    require(transaction->deadline>0 && transaction->child.deadline_ns==transaction->deadline*1000ULL,"original-transaction-deadline-never-renewed");
    if(fault_phase) {
        require(fault_hits==1 && manager_acquisitions==1,"one-finite-original-manager-fault");
        if(!strcmp(fault_phase,"final"))require(invocation_attached==1,"final-fault-after-complete-private-attachment");
        if(!strcmp(fault_phase,"closure"))require(invocation_attached==1 && closure_checks==1,"last-manager-check-after-setup-closure");
        if(!strncmp(fault_kind,"uid-",4) || !strncmp(fault_kind,"gid-",4) || !strncmp(fault_kind,"cap-",4) ||
            !strncmp(fault_kind,"worker-",7) || !strcmp(fault_kind,"starttime") || !strcmp(fault_kind,"userns") || !strcmp(fault_kind,"pidns"))
            require(field_fault_reads>0,"exact-manager-field-fault-consumed");
        require(owner->retained.manager.deadline==transaction->deadline,"manager-retains-original-absolute-deadline");
    }
    if(positive && !manager_exited){identity_snapshot(independent_proc,&identity_after);identity_unchanged(&identity_before,&identity_after);}
    if(!strcmp(expected_stage(mode),"source-clone") || positive || !strcmp(mode,"post-attach-required-drift") ||
        !strcmp(mode,"result-malformed") || !strcmp(mode,"cleanup-failure")) {
        require(clone_seen>0 && manager_acquisitions==1 && owner->retained.manager.unit.pid==(uint32_t)manager_pid,"fault-after-clone-keeps-original-manager");
    }
    if(!strcmp(mode,"post-attach-required-drift"))require(post_attach_drift==1,"late-original-host-fault-injected-once");
    char summary[PATH_MAX];snprintf(summary,sizeof(summary),"%s/transaction-witness.json",base);FILE *witness=fopen(summary,"wx");
    require(witness && fprintf(witness,"{\"stage\":\"%s\",\"deadline\":%llu,\"helper_deadline\":%llu,\"clone_count\":%d,\"manager_acquisitions\":%u}\n",
        transaction->stage,(unsigned long long)transaction->deadline,(unsigned long long)transaction->child.deadline_ns,clone_seen,manager_acquisitions)>0 && fclose(witness)==0,"finite-transaction-witness");
    require(descriptors()==baseline,"exact-caller-descriptor-balance");
    for(int caller=0;caller<4096;caller++) {
        struct stat current;int exists=fstat(caller,&current)==0;
        require(exists==(int)caller_fds[caller],"exact-borrowed-descriptor-set");
        if(exists)require(current.st_dev==caller_objects[caller].st_dev && current.st_ino==caller_objects[caller].st_ino &&
            current.st_mode==caller_objects[caller].st_mode,"unchanged-borrowed-descriptor-identity");
    }
    release_pam();
    unsigned observed_manager=0,observed_records=0;
    observe_tree(held_manager,".",manager_before,&observed_manager,1);observe_tree(held_records,".",records_before,&observed_records,1);
    require(observed_manager==manager_count && observed_records==record_count,"unchanged-complete-manager-and-record-domains");
    require(openat(held_manager,"bin/ambient-tree/nested/leaf",O_WRONLY|O_CLOEXEC)<0 && errno==EROFS,"original-manager-nested-source-remains-readonly");
    close(held_manager);close(held_records);
    if(!strcmp(mode,"exit-after-decision")) {
        require(manager_exited && pwrite(original_source,"X",1,100)==1 && fsync(original_source)==0,"host-replacement-after-manager-decision-exit");
        snprintf(path,sizeof(path),"%s/host/usr/bin/native",base);fd=open(path,O_RDONLY|O_CLOEXEC);char byte;
        require(fd>=0 && pread(fd,&byte,1,100)==1 && byte==original_required_byte && close(fd)==0,"admitted-private-required-copy-survives-manager-death-and-host-drift");
    }
    if(positive){actual_nested();require(mac_calls==1,"gate-final-MAC-once");snprintf(path,sizeof(path),"%s/host/usr/bin/ambient",base);
        require((access(path,F_OK)==0)==(strcmp(mode,"ambient-narrow")!=0),"invocation-ambient-selection");}
    else {
        require(!mac_calls,"refusal-before-final-MAC");struct stat info;struct statx mount;
        snprintf(path,sizeof(path),"%s/host/usr",base);
        require(lstat(path,&info)==0 && statx(AT_FDCWD,path,AT_SYMLINK_NOFOLLOW,STATX_MNT_ID,&mount)==0 &&
            info.st_dev==original_target_info.st_dev && info.st_ino==original_target_info.st_ino &&
            mount.stx_mnt_id==original_target_mount.stx_mnt_id,"refusal-detaches-only-owned-invocation");
    }
    if(!strcmp(mode,"cleanup-failure"))require(cleanup_failures>0,"cleanup-failure-injected-at-owned-detach");
    if(!strcmp(mode,"deadline"))require(clone_seen>0,"original-deadline-expired-after-clone");
    if(strcmp(mode,"exit-after-clone") && !manager_exited)manager_command('x');int status;require(waitpid(manager_pid,&status,0)==manager_pid && WIFEXITED(status) && WEXITSTATUS(status)==0,"owned-manager-reaped");
    if(independently_wrong_usr>=0)close(independently_wrong_usr);
    close(manager_ready);close(manager_release);close(manager_pidfd);close(held_manager_namespace);close(independent_proc);close(original_source);puts("verified");return 0;
}
'''


def _native(helper):
    """Extend maintained fresh fixture boundaries; retain its kernel wrappers."""
    source = fresh.NATIVE.split('int main(int argc,char **argv) {', 1)[0]
    marker = '#define KIOSK_ACCOUNT_NAME'
    source = source.replace(marker, PLATFORM + '\n' + marker, 1)
    source = source.replace('#define pam_get_item fixture_item', '#define pam_get_item retained_item')
    source = source.replace('#define dlopen fixture_dlopen', '#define dlopen retained_dlopen')
    source = source.replace('#define dlsym fixture_dlsym', '#define dlsym retained_dlsym')
    source = source.replace('#define dlclose fixture_dlclose', '#define dlclose retained_dlclose')
    source = source.replace('#define umount2 fixture_umount', '#define umount2 retained_umount')
    source = source.replace('#define mount fixture_mount', '#define mount retained_mount')
    source = source.replace('#include "kiosk_confinement.h"', '''
#define openat retained_openat
#define stat(...) retained_stat(__VA_ARGS__)
#define syscall retained_syscall
#define getline retained_getline
#define open_tree retained_open_tree
#define move_mount retained_move_mount
#define KIOSK_PIN_CLOCK_GETTIME retained_clock_gettime
#define clock_gettime retained_clock_gettime
#define poll retained_poll
#define pam_get_data retained_get_data
#define pam_set_data retained_set_data
#define pam_syslog retained_syslog
#include "kiosk_confinement.h"
#undef openat
#undef stat
#undef syscall
#undef getline
#undef open_tree
#undef move_mount
#undef clock_gettime
#undef poll
#undef pam_get_data
#undef pam_set_data
#undef pam_syslog''')
    source = source.replace('#include <sys/mount.h>', '#include <sys/mount.h>\n#include <sys/mman.h>\n#include <sys/statvfs.h>\n#include <linux/mount.h>\n#include <poll.h>\n#include <pthread.h>')
    return (source + MAIN).replace('@HELPER@', json.dumps(str(helper)))


@pytest.fixture
def retained_scene(fresh_scene):
    directory, _ = fresh_scene
    configuration = directory / ('host' + fresh.PAYLOAD) / 'config.json'
    config = json.loads(configuration.read_text())
    config['executables'][0]['role'] = 'manager'
    config['domains'] = ['manager', 'gate']
    config['apparmor_profiles'] = ['onpc-kiosk-manager', 'onpc-kiosk-gate']
    configuration.write_text(json.dumps(config, sort_keys=True))
    state_path = directory / 'host/var/lib/oh-no-parent-control/kiosk-confinement.json'
    state = json.loads(state_path.read_text())
    state['loaded_config_sha256'] = hashlib.sha256(configuration.read_bytes()).hexdigest()
    state_path.write_text(json.dumps(state))
    (directory / 'host/sys/kernel/security/apparmor/profiles').write_text(
        'onpc-kiosk-manager (enforce)\nonpc-kiosk-gate (enforce)\n')
    helper = directory / 'helper'
    text = helper.read_text().replace("base / 'helper-started', 'x'", "base / 'helper-started', 'w'")
    text = text.replace("    return snapshot, config_bytes\n", "    return snapshot, config_bytes, b'ONPC-KIOSK-ACCOUNT\\t1\\t4242\\t4242\\t1\\n4242\\n'\n")
    # Existing malformed-result controls cover both roles in this composition.
    text = text.replace("record.get('role') == 'manager'", "record.get('role') in ('manager', 'gate')")
    text = text.replace("if mode == 'helper-timeout':\n    import signal", "if mode == 'helper-timeout':\n    (base / 'timeout-waiting').write_text('waiting')\n    import signal")
    helper.write_text(text)
    source = directory / 'retained.c'
    source.write_text(_native(helper))
    binary = directory / 'retained'
    completed = subprocess.run(['cc', '-std=gnu11', '-Wall', '-Wextra', '-Wno-unused-function',
                                '-Wno-format-truncation', '-I', str(fresh.ROOT / 'tools'),
                                str(source), '-ldl', '-lpam', '-pthread', '-o', str(binary)],
                               capture_output=True, text=True, timeout=30,
                               pass_fds=test_storage.scratch_descriptors())
    assert completed.returncode == 0, completed.stderr
    binary.chmod(0o755)
    for target in (directory / 'host/usr/bin/native', directory / 'other-manager'):
        target.write_bytes(binary.read_bytes())
        target.chmod(0o755)
    (directory / 'mode').write_text('healthy')
    return directory, binary


# Reuse the maintained disk-private input allocation as an ordinary pytest
# fixture, rather than invoking its decorated function outside pytest.
fresh_scene = fresh.fresh_scene


@pytest.mark.parametrize('mode', [
    'healthy', 'ambient-narrow', 'same-reexec', 'same-fd-reexec', 'exit-after-decision',
    'wrong-clone', 'missing-nested-clone', 'required-drift', 'post-attach-required-drift', 'absent-ready',
    'stale-ready', 'forged-ready', 'missing-source', 'foreign-source', 'inactive',
    'manager', 'invocation', 'namespace', 'foreign-reexec', 'exit-after-clone',
    'helper-exit', 'helper-timeout', 'result-malformed', 'deadline', 'cleanup-failure',
    'capabilities-inherited', 'capabilities-zero', 'capabilities-get-before', 'capabilities-set',
    'capabilities-ambient', 'capabilities-get-after', 'capabilities-inheritable-drift',
    'capabilities-effective-drift', 'capabilities-permitted-drift',
] + [f'{phase}-{kind}' for phase in ('acquire', 'clone', 'final') for kind in (
    'exit', 'mainpid', 'invocation', 'cgroup', 'root', 'namespace', 'label',
    'uid', 'gid', 'groups', 'capabilities', 'executable', 'tasks',
) if phase != 'clone' or kind not in ('exit', 'mainpid', 'invocation', 'namespace', 'executable')]
  + ['clone-unstable-reexec', 'stable-two-tasks']
  + [f'{phase}-{kind}' for phase in ('acquire', 'clone', 'final') for kind in (
      'boot', 'starttime', 'userns', 'pidns', 'unit-cgroup', 'task-exit', 'worker-uid', 'worker-cap',
      'uid-0', 'uid-1', 'uid-2', 'gid-0', 'gid-1', 'gid-2', 'cap-inh', 'cap-prm', 'cap-amb',
  )]
  + [f'{phase}-cgroup-drift' for phase in ('clone', 'final')]
  + [f'closure-{kind}' for kind in ('exit', 'mainpid', 'invocation', 'root', 'namespace', 'label', 'uid', 'tasks', 'executable')]
  + [f'{phase}-{kind}' for phase in ('acquire', 'final', 'closure') for kind in ('same-reexec', 'fd-reexec')])
def test_exact_pam_fresh_then_retained_transaction(retained_scene, mode):
    directory, binary = retained_scene
    completed = subprocess.run([str(binary), mode, str(directory)],
                               capture_output=True, text=True, timeout=30,
                               pass_fds=test_storage.scratch_descriptors())
    errors = directory / 'helper-error'
    assert completed.returncode == 0, (
        f'{mode}: returncode={completed.returncode}\n{completed.stdout}\n{completed.stderr}\n'
        + (errors.read_text() if errors.exists() else ''))
    assert completed.stdout == 'verified\n'
    witness = json.loads((directory / 'transaction-witness.json').read_text())
    helper_started = json.loads((directory / 'helper-started').read_text())
    assert helper_started['deadline'] == witness['helper_deadline'] == witness['deadline'] * 1000
    if mode == 'helper-timeout':
        assert (directory / 'timeout-waiting').read_text() == 'waiting'
    assert (directory / 'lock').read_bytes() == (directory / 'lease').read_bytes() == b'owned-lock'
    generations = [p for p in (directory / 'runtime').iterdir() if len(p.name) == 64]
    assert len(generations) == 1
    assert not any(p.name.startswith('.runtime-') for p in (directory / 'runtime').iterdir())
