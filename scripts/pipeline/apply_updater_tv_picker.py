"""Replace the Updater's phone file picker with a list of zips that works with a TV remote."""
from pathlib import Path
T=Path('/opt/sabrina/android16/packages/apps/Updater/app/src/main')
def edit(rel,pairs):
    p=T/rel;t=p.read_text();changed=False
    for old,new in pairs:
        if new in t:continue
        assert t.count(old)==1,(rel,old[:60],t.count(old));t=t.replace(old,new);changed=True
    if changed:p.write_text(t)
    print('patched' if changed else 'already patched',rel)
edit('AndroidManifest.xml',[('''    <uses-permission android:name="android.permission.RECOVERY" />''','''    <uses-permission android:name="android.permission.MANAGE_DOCUMENTS" />
    <uses-permission android:name="android.permission.RECOVERY" />'''),
 ('''    <application''','''    <queries>
        <provider android:authorities="com.android.externalstorage.documents" />
    </queries>

    <application''')])
edit('res/values/strings.xml',[('''    <string name="local_update_import_progress">''','''    <string name="local_update_no_files">No zip files found. Copy one to the Download folder or to a USB drive, then try again.</string>
    <string name="local_update_import_progress">''')])
J='java/org/lineageos/updater/'
edit(J+'UpdateImporter.java',[
 ('''import android.content.Intent;
import android.net.Uri;
import android.os.ParcelFileDescriptor;
import android.util.Log;
''','''import android.app.AlertDialog;
import android.content.Intent;
import android.database.Cursor;
import android.net.Uri;
import android.os.ParcelFileDescriptor;
import android.provider.DocumentsContract;
import android.text.format.Formatter;
import android.util.Log;
'''),
 ('''import java.io.IOException;
''','''import java.io.IOException;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;
'''),
 ('''    private static final String FILE_NAME = "localUpdate.zip";
''','''    private static final String FILE_NAME = "localUpdate.zip";
    private static final String STORAGE_AUTHORITY = "com.android.externalstorage.documents";
    private static final int MAX_SCAN_DEPTH = 4;
'''),
 ('''    public void openImportPicker() {
        final Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT)
                .addCategory(Intent.CATEGORY_OPENABLE)
                .setType(MIME_ZIP);
        activity.startActivityForResult(intent, REQUEST_PICK);
    }
''','''    public void openImportPicker() {
        new Thread(() -> {
            final List<LocalZip> zips = findLocalZips();
            activity.runOnUiThread(() -> showLocalZips(zips));
        }).start();
    }

    private void showLocalZips(List<LocalZip> zips) {
        if (activity.isFinishing() || activity.isDestroyed()) {
            return;
        }
        final AlertDialog.Builder dialog = new AlertDialog.Builder(activity)
                .setTitle(R.string.local_update_import)
                .setNegativeButton(android.R.string.cancel, null);
        if (zips.isEmpty()) {
            dialog.setMessage(R.string.local_update_no_files);
        } else {
            final CharSequence[] labels = new CharSequence[zips.size()];
            for (int i = 0; i < labels.length; i++) {
                labels[i] = zips.get(i).label;
            }
            dialog.setItems(labels, (d, which) -> onPicked(zips.get(which).uri));
        }
        dialog.show();
    }

    /** Lists zips on internal storage and USB drives, newest first. */
    private List<LocalZip> findLocalZips() {
        final List<LocalZip> zips = new ArrayList<>();
        final Set<String> seen = new HashSet<>();
        final String[] columns = {
                DocumentsContract.Root.COLUMN_DOCUMENT_ID,
                DocumentsContract.Root.COLUMN_TITLE,
        };
        try (Cursor roots = activity.getContentResolver().query(
                DocumentsContract.buildRootsUri(STORAGE_AUTHORITY), columns, null, null, null)) {
            while (roots != null && roots.moveToNext()) {
                findLocalZips(roots.getString(0), roots.getString(1), 0, seen, zips);
            }
        } catch (RuntimeException e) {
            Log.e(TAG, "Failed to list storage", e);
        }
        zips.sort((a, b) -> Long.compare(b.modified, a.modified));
        return zips;
    }

    private void findLocalZips(String documentId, String location, int depth, Set<String> seen,
            List<LocalZip> zips) {
        if (depth > MAX_SCAN_DEPTH || !seen.add(documentId)) {
            return;
        }
        final String[] columns = {
                DocumentsContract.Document.COLUMN_DOCUMENT_ID,
                DocumentsContract.Document.COLUMN_DISPLAY_NAME,
                DocumentsContract.Document.COLUMN_MIME_TYPE,
                DocumentsContract.Document.COLUMN_LAST_MODIFIED,
                DocumentsContract.Document.COLUMN_SIZE,
        };
        try (Cursor children = activity.getContentResolver().query(
                DocumentsContract.buildChildDocumentsUri(STORAGE_AUTHORITY, documentId),
                columns, null, null, null)) {
            while (children != null && children.moveToNext()) {
                final String id = children.getString(0);
                final String name = children.getString(1);
                if (DocumentsContract.Document.MIME_TYPE_DIR.equals(children.getString(2))) {
                    if (!"Android".equals(name)) {
                        findLocalZips(id, location + "/" + name, depth + 1, seen, zips);
                    }
                } else if (name != null && name.toLowerCase(Locale.ROOT).endsWith(".zip")
                        && seen.add(id)) {
                    zips.add(new LocalZip(
                            DocumentsContract.buildDocumentUri(STORAGE_AUTHORITY, id),
                            name + "\\n" + location + " - "
                                    + Formatter.formatShortFileSize(activity, children.getLong(4)),
                            children.getLong(3)));
                }
            }
        } catch (RuntimeException e) {
            Log.w(TAG, "Skipping " + location, e);
        }
    }

    private static final class LocalZip {
        final Uri uri;
        final String label;
        final long modified;

        LocalZip(Uri uri, String label, long modified) {
            this.uri = uri;
            this.label = label;
            this.modified = modified;
        }
    }
''')])
# Start with something selected, so the remote works as soon as the screen opens.
edit(J+'UpdatesScaffoldActivity.kt',[
 ('''    Category {
''','''    val focusRequester = remember { FocusRequester() }
    LaunchedEffect(Unit) { focusRequester.requestFocus() }

    Category(modifier = Modifier.focusRequester(focusRequester).focusGroup()) {
'''),
 ('''import androidx.compose.foundation.layout.Column
''','''import androidx.compose.foundation.focusGroup
import androidx.compose.foundation.layout.Column
'''),
 ('''import androidx.compose.runtime.CompositionLocalProvider
''','''import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.LaunchedEffect
'''),
 ('''import androidx.compose.ui.platform.LocalDensity
''','''import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.platform.LocalDensity
''')])
print('done')
