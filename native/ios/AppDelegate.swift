import UIKit
import WebKit
import Capacitor

@UIApplicationMain
class AppDelegate: UIResponder, UIApplicationDelegate {

    var window: UIWindow?
    private var webViewLoadingObservation: NSKeyValueObservation?
    private var didHideLaunchSplash = false
    private var webViewDidStartLoading = false
    private var splashWatchAttempts = 0

    func application(_ application: UIApplication, didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]?) -> Bool {
        DispatchQueue.main.async { [weak self] in
            self?.hideSplashWhenWebViewIsReady()
        }
        return true
    }

    func applicationWillResignActive(_ application: UIApplication) {
        // Sent when the application is about to move from active to inactive state. This can occur for certain types of temporary interruptions (such as an incoming phone call or SMS message) or when the user quits the application and it begins the transition to the background state.
        // Use this method to pause ongoing tasks, disable timers, and invalidate graphics rendering callbacks. Games should use this method to pause the game.
    }

    func applicationDidEnterBackground(_ application: UIApplication) {
        // Use this method to release shared resources, save user data, invalidate timers, and store enough application state information to restore your application to its current state in case it is terminated later.
        // If your application supports background execution, this method is called instead of applicationWillTerminate: when the user quits.
    }

    func applicationWillEnterForeground(_ application: UIApplication) {
        // Called as part of the transition from the background to the active state; here you can undo many of the changes made on entering the background.
    }

    func applicationDidBecomeActive(_ application: UIApplication) {
        // Restart any tasks that were paused (or not started) while the application was inactive. If the application was previously in the background, optionally refresh the user interface.
    }

    func applicationWillTerminate(_ application: UIApplication) {
        // Called when the application is about to terminate. Save data if appropriate. See also applicationDidEnterBackground:.
    }

    func application(_ app: UIApplication, open url: URL, options: [UIApplication.OpenURLOptionsKey: Any] = [:]) -> Bool {
        // Called when the app was launched with a url. Feel free to add additional processing here,
        // but if you want the App API to support tracking app url opens, make sure to keep this call
        return ApplicationDelegateProxy.shared.application(app, open: url, options: options)
    }

    func application(_ application: UIApplication, continue userActivity: NSUserActivity, restorationHandler: @escaping ([UIUserActivityRestoring]?) -> Void) -> Bool {
        // Called when the app was launched with an activity, including Universal Links.
        // Feel free to add additional processing here, but if you want the App API to support
        // tracking app url opens, make sure to keep this call
        return ApplicationDelegateProxy.shared.application(application, continue: userActivity, restorationHandler: restorationHandler)
    }

    private func hideSplashWhenWebViewIsReady() {
        guard !didHideLaunchSplash else { return }

        guard let capVC = window?.rootViewController as? CAPBridgeViewController,
              let webView = capVC.webView ?? findWebView(in: capVC.view) else {
            splashWatchAttempts += 1
            guard splashWatchAttempts < 100 else { return }
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.05) { [weak self] in
                self?.hideSplashWhenWebViewIsReady()
            }
            return
        }

        let hideNow = { [weak self] in
            guard let self = self, !self.didHideLaunchSplash else { return }
            self.didHideLaunchSplash = true
            self.webViewLoadingObservation?.invalidate()
            self.webViewLoadingObservation = nil
            self.hideSplashOverlay(from: capVC)
        }

        // Remote page already finished (for example from cache) — hide immediately.
        if webView.url != nil, !webView.isLoading {
            hideNow()
            return
        }

        if webView.isLoading {
            webViewDidStartLoading = true
        }

        webViewLoadingObservation = webView.observe(\.isLoading, options: [.new]) { [weak self] _, change in
            guard let self = self else { return }
            if change.newValue == true {
                self.webViewDidStartLoading = true
            } else if self.webViewDidStartLoading {
                hideNow()
            }
        }
    }

    private func hideSplashOverlay(from capVC: CAPBridgeViewController) {
        if let plugin = capVC.bridge?.plugin(withName: "SplashScreen") {
            let call = CAPPluginCall(
                callbackId: "hide-splash",
                methodName: "hide",
                options: ["fadeOutDuration": 0],
                success: { _, _ in },
                error: { _ in }
            )
            plugin.perform(NSSelectorFromString("hide:"), with: call)
            return
        }

        capVC.bridge?.eval(js: "window.Capacitor && Capacitor.Plugins && Capacitor.Plugins.SplashScreen && Capacitor.Plugins.SplashScreen.hide({ fadeOutDuration: 0 });")
    }

    private func findWebView(in view: UIView?) -> WKWebView? {
        guard let view = view else { return nil }
        if let webView = view as? WKWebView {
            return webView
        }
        for subview in view.subviews {
            if let found = findWebView(in: subview) {
                return found
            }
        }
        return nil
    }

}
