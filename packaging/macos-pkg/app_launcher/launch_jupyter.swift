import AppKit
import Foundation

final class LauncherAppDelegate: NSObject, NSApplicationDelegate {
    private let home = FileManager.default.homeDirectoryForCurrentUser.path
    private lazy var appRoot = "\(home)/Library/Application Support/kymflow-pkg"
    private lazy var workspaceRoot = "\(home)/Documents/KymFlow"
    private lazy var jupyterBin = "\(appRoot)/venv/bin/jupyter"
    private lazy var logDir = "\(appRoot)/logs"
    private lazy var runtimeLog = "\(logDir)/jupyter-app-runtime.log"
    private lazy var browserURL = URL(string: "http://127.0.0.1:8888/lab")!

    private var childProcess: Process?

    func applicationDidFinishLaunching(_ notification: Notification) {
        do {
            try FileManager.default.createDirectory(atPath: logDir, withIntermediateDirectories: true)
            log("=== KymFlow Jupyter launcher start ===")
            log("appRoot=\(appRoot)")
            log("workspaceRoot=\(workspaceRoot)")
            log("jupyterBin=\(jupyterBin)")
        } catch {
            failAndExit("Unable to initialize log directory: \(error)")
            return
        }

        guard FileManager.default.isExecutableFile(atPath: jupyterBin) else {
            failAndExit("Jupyter executable not found: \(jupyterBin)")
            return
        }

        do {
            try FileManager.default.createDirectory(atPath: workspaceRoot, withIntermediateDirectories: true)
        } catch {
            failAndExit("Unable to create workspace directory: \(error)")
            return
        }

        if isPort8888Listening() {
            log("Port 8888 already listening; opening existing server URL and exiting launcher.")
            NSWorkspace.shared.open(browserURL)
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.3) {
                NSApp.terminate(nil)
            }
            return
        }

        let process = Process()
        process.executableURL = URL(fileURLWithPath: jupyterBin)
        process.arguments = ["lab", "--notebook-dir=\(workspaceRoot)"]
        process.currentDirectoryURL = URL(fileURLWithPath: workspaceRoot)

        guard let logHandle = openLogHandle() else {
            failAndExit("Could not open runtime log at \(runtimeLog)")
            return
        }
        process.standardOutput = logHandle
        process.standardError = logHandle

        process.terminationHandler = { [weak self] proc in
            guard let self else { return }
            self.log("Jupyter child exited status=\(proc.terminationStatus)")
            DispatchQueue.main.async {
                NSApp.terminate(nil)
            }
        }

        do {
            try process.run()
            childProcess = process
            log("Spawned Jupyter child PID=\(process.processIdentifier)")
        } catch {
            failAndExit("Failed to launch Jupyter child: \(error)")
        }
    }

    func applicationShouldTerminate(_ sender: NSApplication) -> NSApplication.TerminateReply {
        guard let process = childProcess, process.isRunning else {
            return .terminateNow
        }

        log("Quit requested; terminating child PID=\(process.processIdentifier)")
        process.terminate()

        let deadline = Date().addingTimeInterval(3.0)
        while process.isRunning && Date() < deadline {
            Thread.sleep(forTimeInterval: 0.1)
        }

        if process.isRunning {
            log("Child still running after grace period; force kill PID=\(process.processIdentifier)")
            kill(process.processIdentifier, SIGKILL)
        }

        return .terminateNow
    }

    private func openLogHandle() -> FileHandle? {
        if !FileManager.default.fileExists(atPath: runtimeLog) {
            FileManager.default.createFile(atPath: runtimeLog, contents: nil)
        }
        guard let handle = FileHandle(forWritingAtPath: runtimeLog) else {
            return nil
        }
        do {
            try handle.seekToEnd()
        } catch {
            return nil
        }
        return handle
    }

    private func isPort8888Listening() -> Bool {
        let probe = Process()
        probe.executableURL = URL(fileURLWithPath: "/usr/sbin/lsof")
        probe.arguments = ["-nP", "-iTCP:8888", "-sTCP:LISTEN"]
        let outputPipe = Pipe()
        probe.standardOutput = outputPipe
        probe.standardError = Pipe()
        do {
            try probe.run()
            probe.waitUntilExit()
        } catch {
            log("Port probe failed (\(error)); assuming no existing server.")
            return false
        }
        let data = outputPipe.fileHandleForReading.readDataToEndOfFile()
        guard let text = String(data: data, encoding: .utf8) else {
            return false
        }
        // lsof prints a header line first; second line means at least one listener.
        return text.split(separator: "\n").count >= 2
    }

    private func failAndExit(_ message: String) {
        log("ERROR: \(message)")
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.1) {
            NSApp.terminate(nil)
        }
    }

    private func log(_ message: String) {
        let timestamp = ISO8601DateFormatter().string(from: Date())
        let line = "[\(timestamp)] \(message)\n"
        if let data = line.data(using: .utf8) {
            if !FileManager.default.fileExists(atPath: runtimeLog) {
                FileManager.default.createFile(atPath: runtimeLog, contents: nil)
            }
            if let handle = FileHandle(forWritingAtPath: runtimeLog) {
                do {
                    try handle.seekToEnd()
                    try handle.write(contentsOf: data)
                    try handle.close()
                } catch {
                    fputs(line, stderr)
                }
            } else {
                fputs(line, stderr)
            }
        }
    }
}

let app = NSApplication.shared
let delegate = LauncherAppDelegate()
app.setActivationPolicy(.regular)
app.delegate = delegate
app.run()
