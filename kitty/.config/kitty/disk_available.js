// Finder-style available capacity, including storage macOS can reclaim.
ObjC.import("Foundation");

function run() {
    var url = $.NSURL.fileURLWithPath("/System/Volumes/Data");
    var capacity = Ref();
    var error = Ref();
    if (!url.getResourceValueForKeyError(
        capacity, $.NSURLVolumeAvailableCapacityForImportantUsageKey, error
    )) {
        throw Error("Unable to read available disk capacity");
    }
    return String(ObjC.unwrap(capacity[0]));
}
