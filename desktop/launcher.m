#import <Cocoa/Cocoa.h>
#import <mach-o/dyld.h>
#include <limits.h>
#include <unistd.h>

@interface YingxuLauncher : NSObject <NSApplicationDelegate>
@property(nonatomic, copy) NSString *servicePath;
@property(nonatomic) NSTimeInterval lastLaunch;
@property(nonatomic, strong) NSTask *browserTask;
@end

@implementation YingxuLauncher
- (void)openWorkbench {
    NSLog(@"Open workbench requested; helper running=%d", self.browserTask.running);
    if (self.browserTask.running) return;
    NSTimeInterval now = [NSDate timeIntervalSinceReferenceDate];
    if (now - self.lastLaunch < 1.0) return;
    self.lastLaunch = now;
    NSTask *task = [[NSTask alloc] init];
    task.executableURL = [NSURL fileURLWithPath:self.servicePath];
    task.arguments = @[@"--no-browser"];
    NSError *error = nil;
    if (![task launchAndReturnError:&error]) {
        NSAlert *alert = [[NSAlert alloc] init];
        alert.messageText = @"映序启动失败";
        alert.informativeText = error.localizedDescription;
        [alert runModal];
        return;
    }
    NSString *helper = [[self.servicePath stringByDeletingLastPathComponent] stringByAppendingPathComponent:@"../open-workbench.py"];
    NSTask *browser = [[NSTask alloc] init];
    browser.executableURL = task.executableURL;
    browser.arguments = @[@"-c", @"import runpy,sys; runpy.run_path(sys.argv[3], run_name='__main__')", helper];
    NSString *logPath = [NSHomeDirectory() stringByAppendingPathComponent:@"Library/Application Support/Yingxu/launcher.log"];
    NSFileHandle *log = [NSFileHandle fileHandleForWritingAtPath:logPath];
    [log seekToEndOfFile];
    browser.standardOutput = log;
    browser.standardError = log;
    browser.terminationHandler = ^(NSTask *finished) {
        NSLog(@"Chrome helper exited with status %d", finished.terminationStatus);
    };
    self.browserTask = browser;
    if (![browser launchAndReturnError:&error]) {
        NSLog(@"Chrome open failed: %@", error.localizedDescription);
    }
}
- (void)applicationDidFinishLaunching:(NSNotification *)notification {
    [self openWorkbench];
}
- (BOOL)applicationShouldHandleReopen:(NSApplication *)sender hasVisibleWindows:(BOOL)flag {
    [self openWorkbench];
    return YES;
}
@end

int main(int argc, char **argv) {
    @autoreleasepool {
        char raw[PATH_MAX], resolved[PATH_MAX];
        uint32_t size = sizeof(raw);
        if (_NSGetExecutablePath(raw, &size) != 0 || !realpath(raw, resolved)) return 1;
        NSString *directory = [[NSString stringWithUTF8String:resolved] stringByDeletingLastPathComponent];
        NSString *service = [directory stringByAppendingPathComponent:@"../Resources/engine/YingxuService"];
        if (argc > 1 && strncmp(argv[1], "-psn_", 5) != 0) {
            argv[0] = (char *)service.fileSystemRepresentation;
            execv(argv[0], argv);
            return 1;
        }
        NSString *logs = [NSHomeDirectory() stringByAppendingPathComponent:@"Library/Application Support/Yingxu"];
        [[NSFileManager defaultManager] createDirectoryAtPath:logs withIntermediateDirectories:YES attributes:nil error:nil];
        freopen([[logs stringByAppendingPathComponent:@"launcher.log"] fileSystemRepresentation], "a", stderr);
        NSApplication *application = [NSApplication sharedApplication];
        [application setActivationPolicy:NSApplicationActivationPolicyAccessory];
        __attribute__((objc_precise_lifetime)) YingxuLauncher *delegate = [[YingxuLauncher alloc] init];
        delegate.servicePath = service;
        application.delegate = delegate;
        [application run];
    }
    return 0;
}
