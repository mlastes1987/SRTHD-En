using System;
using System.IO;
using System.Linq;
using System.Collections.Generic;
using System.Web.Script.Serialization;
using System.Drawing;
using System.Windows.Forms;
using System.IO.Compression;
using System.Text;
using SRWEnglish;

public static class InstallerTests
{
    static void Assert(bool value,string message) {if(!value)throw new Exception(message);}
    static void Fails(Action action,string message)
    { bool failed=false;try{action();}catch{failed=true;}Assert(failed,message); }
    static string FilePath(string game,PatchFile f) {return Core.Inside(Path.Combine(game,"USRDIR"),f.path);}
    [STAThread] public static int Main(string[] args)
    {
        try
        {
            var package=args[0];var game=args[1];var elf=args[2];var core=new Core(package,game);
            var original=core.Manifest.files.ToDictionary(f=>f.path,f=>Core.HashFile(FilePath(game,f)));
            Action originals=delegate {foreach(var f in core.Manifest.files)Assert(Core.HashFile(FilePath(game,f))==original[f.path],"Original changed: "+f.path);};
            Action translated=delegate {foreach(var f in core.Manifest.files)Assert(Core.HashFile(FilePath(game,f))==f.target_sha256,"Target mismatch: "+f.path);};
            core.Check(); originals();
            var first=FilePath(game,core.Manifest.files[0]);var bytes=File.ReadAllBytes(first);
            var wrong=(byte[])bytes.Clone();wrong[wrong.Length-1]^=1;File.WriteAllBytes(first,wrong);
            Fails(delegate{core.Install(null,elf);},"Wrong version was accepted");
            Assert(Core.HashFile(first)==Core.Hash(wrong),"Wrong-version rejection changed files");File.WriteAllBytes(first,bytes);
            Core.FaultAfter=1;
            Fails(delegate{core.Install(null,elf);},"Injected failure did not fire");originals();
            Core.FaultAfter=-1;
            core.Install(null,elf);translated();
            var backup=Path.Combine(game,".srwt1-english","backups","EBOOT.BIN");
            Assert(Core.HashFile(backup)==original["EBOOT.BIN"],"Backup did not preserve encrypted EBOOT");
            core.Install(null,elf);translated();
            Assert(Core.HashFile(backup)==original["EBOOT.BIN"],"Reinstall overwrote original backup");
            var updateDir=Path.Combine(Path.GetDirectoryName(game),"update-package");Directory.CreateDirectory(updateDir);
            var json=new JavaScriptSerializer();
            var update=json.Deserialize<Manifest>(json.Serialize(core.Manifest));update.version="test-update";
            foreach(var f in update.files)
            {var dst=Core.Inside(updateDir,f.patch);Directory.CreateDirectory(Path.GetDirectoryName(dst));File.Copy(Core.Inside(package,f.patch),dst);}
            var entry=update.files[0];
            var updated=Core.Apply(File.ReadAllBytes(elf),File.ReadAllBytes(Core.Inside(package,entry.patch)),entry.target_size);
            updated[updated.Length-1]^=1;
            byte[] updatePatch;
            using(var output=new MemoryStream())
            {
                using(var compression=new DeflateStream(output,CompressionMode.Compress,true))
                using(var writer=new BinaryWriter(compression))
                {writer.Write(Encoding.ASCII.GetBytes("SRWDIF01"));writer.Write((long)updated.Length);writer.Write((byte)'A');writer.Write(updated.Length);writer.Write(updated);writer.Write((byte)'E');}
                updatePatch=output.ToArray();
            }
            File.WriteAllBytes(Core.Inside(updateDir,entry.patch),updatePatch);
            entry.patch_sha256=Core.Hash(updatePatch);entry.target_sha256=Core.Hash(updated);
            File.WriteAllText(Path.Combine(updateDir,"manifest.json"),json.Serialize(update));
            var upgrade=new Core(updateDir,game);
            Core.FaultAfter=1;Fails(delegate{upgrade.Install(null,elf);},"Upgrade failure did not fire");translated();
            // The old installed hashes remain recognizable after rollback.
            upgrade.Check();Core.FaultAfter=-1;upgrade.Install(null,elf);
            Assert(Core.HashFile(first)==entry.target_sha256,"Upgrade target mismatch");
            // Simulate a completed commit with its last state write interrupted.
            var statePath=Path.Combine(game,".srwt1-english","state.json");
            var state=json.Deserialize<State>(File.ReadAllText(statePath));state.status="installing";
            File.WriteAllText(statePath,json.Serialize(state));upgrade.Install(null,elf);
            Assert(json.Deserialize<State>(File.ReadAllText(statePath)).status=="installed","Interrupted state not recovered");
            core.Restore();originals();core.Install(null,elf);translated();
            File.WriteAllBytes(first,wrong);
            Fails(delegate{core.Restore();},"Restore overwrote a later modification");
            Assert(Core.HashFile(first)==Core.Hash(wrong),"Restore rejection changed modified file");
            File.WriteAllBytes(first,Core.Apply(File.ReadAllBytes(elf),File.ReadAllBytes(Core.Inside(package,core.Manifest.files[0].patch)),core.Manifest.files[0].target_size));
            core.Restore();originals();core.Restore();originals();
            // A damaged payload is rejected before a single game file changes.
            var patch=Core.Inside(package,core.Manifest.files[1].patch);var goodPatch=File.ReadAllBytes(patch);
            try{File.WriteAllBytes(patch,new byte[]{1,2,3});Fails(delegate{core.Install(null,elf);},"Damaged patch accepted");originals();}
            finally{File.WriteAllBytes(patch,goodPatch);}
            Fails(delegate{Core.Inside(game,"../outside");},"Path traversal accepted");
            Console.WriteLine("PASS: source/payload rejection, verified delta outputs, rollback/retry, idempotence, upgrades, interrupted recovery, backup integrity, restore refusal, restore, path confinement.");
            if(args.Length>3)
            {
                using(var form=new Window(package))
                using(var bitmap=new Bitmap(form.ClientSize.Width,form.ClientSize.Height))
                {
                    using(var graphics=Graphics.FromImage(bitmap))graphics.Clear(form.BackColor);
                    form.CreateControl();form.PerformLayout();
                    foreach(Control control in form.Controls)control.DrawToBitmap(bitmap,control.Bounds);
                    bitmap.Save(args[3]);
                }
            }
            return 0;
        }
        catch(Exception e){Console.Error.WriteLine(e.ToString());return 1;}
    }
}
