#import <Cocoa/Cocoa.h>
#import <WebKit/WebKit.h>
#import <mach-o/dyld.h>
#include <limits.h>
#include <unistd.h>

@interface YingxuLauncher : NSObject <NSApplicationDelegate, WKNavigationDelegate, WKUIDelegate>
@property(nonatomic, copy) NSString *servicePath;
@property(nonatomic, copy) NSString *environmentRoot;
@property(nonatomic) NSTimeInterval lastLaunch;
@property(nonatomic, strong) NSTask *serviceTask;
@property(nonatomic, strong) NSTimer *sessionTimer;
@property(nonatomic, strong) NSWindow *window;
@property(nonatomic, strong) WKWebView *webView;
@end

@implementation YingxuLauncher
- (void)showWorkbenchAtPort:(NSInteger)port {
    NSURL *url = [NSURL URLWithString:[NSString stringWithFormat:@"http://127.0.0.1:%ld/demo/", (long)port]];
    NSURLSessionDataTask *check = [[NSURLSession sharedSession] dataTaskWithURL:url completionHandler:^(NSData *data, NSURLResponse *response, NSError *error) {
        dispatch_async(dispatch_get_main_queue(), ^{
            NSHTTPURLResponse *http = (NSHTTPURLResponse *)response;
            if (error || http.statusCode != 200) return;
            [self.sessionTimer invalidate];
            self.sessionTimer = nil;
            [self loadWorkbench:url];
        });
    }];
    [check resume];
}

- (void)loadWorkbench:(NSURL *)url {
    if (!self.window) {
        NSRect frame = NSMakeRect(0, 0, 1440, 960);
        self.window = [[NSWindow alloc] initWithContentRect:frame
            styleMask:NSWindowStyleMaskTitled | NSWindowStyleMaskClosable | NSWindowStyleMaskMiniaturizable | NSWindowStyleMaskResizable
            backing:NSBackingStoreBuffered defer:NO];
        self.window.title = [[NSBundle mainBundle] objectForInfoDictionaryKey:@"CFBundleName"];
        self.window.minSize = NSMakeSize(980, 700);
        [self.window center];
        WKWebViewConfiguration *configuration = [[WKWebViewConfiguration alloc] init];
        configuration.preferences.javaScriptCanOpenWindowsAutomatically = YES;
        self.webView = [[WKWebView alloc] initWithFrame:frame configuration:configuration];
        self.webView.navigationDelegate = self;
        self.webView.UIDelegate = self;
        self.webView.allowsBackForwardNavigationGestures = YES;
        self.window.contentView = self.webView;
    }
    [self.webView loadRequest:[NSURLRequest requestWithURL:url]];
    [self.window makeKeyAndOrderFront:self];
    [NSApp activateIgnoringOtherApps:YES];
}

- (void)openWorkbench {
    NSTimeInterval now = [NSDate timeIntervalSinceReferenceDate];
    if (now - self.lastLaunch < 1.0) return;
    self.lastLaunch = now;
    if (self.window) {
        [self.window makeKeyAndOrderFront:self];
        [NSApp activateIgnoringOtherApps:YES];
        return;
    }
    if (self.sessionTimer.valid) return;
    if (!self.serviceTask.running) {
        NSTask *task = [[NSTask alloc] init];
        task.executableURL = [NSURL fileURLWithPath:self.servicePath];
        task.arguments = @[@"--no-browser"];
        NSMutableDictionary *environment = [[NSProcessInfo processInfo].environment mutableCopy];
        environment[@"PYTHONDONTWRITEBYTECODE"] = @"1";
        if (self.environmentRoot) {
            environment[@"CONTENT_AGENT_ROOT"] = self.environmentRoot;
        }
        task.environment = environment;
        NSError *error = nil;
        self.serviceTask = task;
        if (![task launchAndReturnError:&error]) {
            NSAlert *alert = [[NSAlert alloc] init];
            alert.messageText = @"映序启动失败";
            alert.informativeText = error.localizedDescription;
            [alert runModal];
            return;
        }
    }
    self.sessionTimer = [NSTimer scheduledTimerWithTimeInterval:0.5 repeats:YES block:^(NSTimer *timer) {
        NSString *pointerPath = [NSHomeDirectory() stringByAppendingPathComponent:@"Library/Application Support/Yingxu/workspace.json"];
        NSData *pointerData = [NSData dataWithContentsOfFile:pointerPath];
        if (!pointerData && !self.environmentRoot) return;
        NSDictionary *pointer = pointerData ? [NSJSONSerialization JSONObjectWithData:pointerData options:0 error:nil] : @{};
        NSString *root = self.environmentRoot ?: pointer[@"root"];
        if (!root) return;
        NSString *sessionPath = [root stringByAppendingPathComponent:@"data/desktop-session.json"];
        NSData *sessionData = [NSData dataWithContentsOfFile:sessionPath];
        if (!sessionData) return;
        NSDictionary *session = [NSJSONSerialization JSONObjectWithData:sessionData options:0 error:nil];
        NSInteger port = [session[@"port"] integerValue];
        if (port > 0) [self showWorkbenchAtPort:port];
    }];
    [self.sessionTimer fire];
}

- (void)applicationDidFinishLaunching:(NSNotification *)notification {
    [self openWorkbench];
}

- (BOOL)applicationShouldHandleReopen:(NSApplication *)sender hasVisibleWindows:(BOOL)flag {
    [self openWorkbench];
    return YES;
}

- (void)webView:(WKWebView *)webView runOpenPanelWithParameters:(WKOpenPanelParameters *)parameters initiatedByFrame:(WKFrameInfo *)frame completionHandler:(void (^)(NSArray<NSURL *> * _Nullable URLs))completionHandler {
    NSOpenPanel *panel = [NSOpenPanel openPanel];
    panel.allowsMultipleSelection = parameters.allowsMultipleSelection;
    panel.canChooseDirectories = parameters.allowsDirectories;
    panel.canChooseFiles = YES;
    [panel beginSheetModalForWindow:self.window completionHandler:^(NSModalResponse result) {
        if (result == NSModalResponseOK) {
            completionHandler(panel.URLs);
            return;
        }
        completionHandler(nil);
    }];
}

- (WKWebView *)webView:(WKWebView *)webView createWebViewWithConfiguration:(WKWebViewConfiguration *)configuration forNavigationAction:(WKNavigationAction *)navigationAction windowFeatures:(WKWindowFeatures *)windowFeatures {
    if (!navigationAction.targetFrame) {
        [[NSWorkspace sharedWorkspace] openURL:navigationAction.request.URL];
    }
    return nil;
}

- (void)webView:(WKWebView *)webView didFailNavigation:(WKNavigation *)navigation withError:(NSError *)error {
    NSLog(@"Workbench navigation failed: %@", error.localizedDescription);
}

- (void)webView:(WKWebView *)webView didFailProvisionalNavigation:(WKNavigation *)navigation withError:(NSError *)error {
    NSLog(@"Workbench provisional navigation failed: %@", error.localizedDescription);
}
@end

int main(int argc, char **argv) {
    @autoreleasepool {
        char raw[PATH_MAX], resolved[PATH_MAX];
        uint32_t size = sizeof(raw);
        if (_NSGetExecutablePath(raw, &size) != 0 || !realpath(raw, resolved)) return 1;
        NSString *directory = [[NSString stringWithUTF8String:resolved] stringByDeletingLastPathComponent];
        NSString *service = [directory stringByAppendingPathComponent:@"../Resources/engine/YingxuService"];
        NSString *environmentRoot = nil;
        if (argc > 2 && strcmp(argv[1], "--ui-root") == 0) {
            environmentRoot = [NSString stringWithUTF8String:argv[2]];
        }
        if (!environmentRoot && argc > 1 && strncmp(argv[1], "-psn_", 5) != 0) {
            argv[0] = (char *)service.fileSystemRepresentation;
            execv(argv[0], argv);
            return 1;
        }
        NSString *logs = [NSHomeDirectory() stringByAppendingPathComponent:@"Library/Application Support/Yingxu"];
        [[NSFileManager defaultManager] createDirectoryAtPath:logs withIntermediateDirectories:YES attributes:nil error:nil];
        freopen([[logs stringByAppendingPathComponent:@"launcher.log"] fileSystemRepresentation], "a", stderr);
        NSApplication *application = [NSApplication sharedApplication];
        [application setActivationPolicy:NSApplicationActivationPolicyRegular];
        __attribute__((objc_precise_lifetime)) YingxuLauncher *delegate = [[YingxuLauncher alloc] init];
        delegate.servicePath = service;
        delegate.environmentRoot = environmentRoot;
        application.delegate = delegate;
        [application run];
    }
    return 0;
}
