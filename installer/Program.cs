using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.IO.Compression;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using System.Web.Script.Serialization;
using System.Windows.Forms;

namespace SRWEnglish
{
    public sealed class PatchFile
    {
        public string path, patch, source_sha256, original_sha256, target_sha256, patch_sha256;
        public long target_size;
        public bool decrypt;
    }
    public sealed class Manifest
    {
        public int format;
        public string title_id, name, version, channel;
        public PatchFile[] files;
    }
    public sealed class State
    {
        public string version, status;
        public Dictionary<string,string> installed = new Dictionary<string,string>();
        public Dictionary<string,string> previous = new Dictionary<string,string>();
    }
    public sealed class Core
    {
        public readonly string Package, Game;
        public readonly Manifest Manifest;
        public Action<string> Log = delegate {};
        internal static int FaultAfter = -1; // used only by the compiled test harness
        static readonly JavaScriptSerializer Json = new JavaScriptSerializer();
        static readonly string[] Allowed = {"EBOOT.BIN", "DATA/KURODATA/KDATAPS3.CPK", "DATA/PIECE/PIECE1STPS3.CPK"};
        string Data { get { return Path.Combine(Game,".srwt1-english"); } }
        string StatePath { get { return Path.Combine(Data,"state.json"); } }
        public static string Hash(byte[] data)
        { using (var sha = SHA256.Create()) return BitConverter.ToString(sha.ComputeHash(data)).Replace("-","").ToLowerInvariant(); }
        public static string HashFile(string path) { return Hash(File.ReadAllBytes(path)); }
        public static string Inside(string root, string relative)
        {
            if (String.IsNullOrWhiteSpace(relative) || Path.IsPathRooted(relative)) throw new Exception("Invalid package path.");
            var full = Path.GetFullPath(Path.Combine(root,relative.Replace('/',Path.DirectorySeparatorChar)));
            var prefix = Path.GetFullPath(root).TrimEnd(Path.DirectorySeparatorChar)+Path.DirectorySeparatorChar;
            if (!full.StartsWith(prefix,StringComparison.OrdinalIgnoreCase)) throw new Exception("Package path leaves its folder.");
            return full;
        }
        static string TitleId(string sfo)
        {
            using (var r = new BinaryReader(File.OpenRead(sfo)))
            {
                if (r.ReadUInt32()!=0x46535000) throw new Exception("Invalid PARAM.SFO.");
                r.ReadUInt32(); uint keys=r.ReadUInt32(), values=r.ReadUInt32(), count=r.ReadUInt32();
                if (count>1024) throw new Exception("Invalid PARAM.SFO table.");
                for (uint i=0;i<count;i++)
                {
                    r.BaseStream.Position=20+i*16; uint key=r.ReadUInt16(); r.ReadUInt16();
                    uint length=r.ReadUInt32(); r.ReadUInt32(); uint value=r.ReadUInt32();
                    r.BaseStream.Position=keys+key;
                    var name=new List<byte>(); byte b;
                    while ((b=r.ReadByte())!=0 && name.Count<128) name.Add(b);
                    if (Encoding.UTF8.GetString(name.ToArray())=="TITLE_ID")
                    { r.BaseStream.Position=values+value; return Encoding.UTF8.GetString(r.ReadBytes((int)Math.Min(length,64))).TrimEnd('\0'); }
                }
            }
            throw new Exception("TITLE_ID missing from PARAM.SFO.");
        }
        public static string ResolveGame(string selection)
        {
            if (String.IsNullOrWhiteSpace(selection)) throw new Exception("Choose the installed NPJB00514 game folder.");
            var root=Path.GetFullPath(selection);
            if (String.Equals(Path.GetFileName(root.TrimEnd('\\','/')),"USRDIR",StringComparison.OrdinalIgnoreCase)) root=Path.GetDirectoryName(root);
            foreach (var suffix in new[] {"", "NPJB00514", "game/NPJB00514", "dev_hdd0/game/NPJB00514"})
            {
                var candidate=Path.Combine(root,suffix.Replace('/',Path.DirectorySeparatorChar));
                if (File.Exists(Path.Combine(candidate,"PARAM.SFO")) && Directory.Exists(Path.Combine(candidate,"USRDIR")))
                {
                    if (TitleId(Path.Combine(candidate,"PARAM.SFO"))!="NPJB00514") throw new Exception("This is not the supported NPJB00514 game.");
                    return candidate;
                }
            }
            throw new Exception("No NPJB00514 game installation found in that folder.");
        }
        public Core(string package, string game)
        {
            Package=Path.GetFullPath(package); Game=ResolveGame(game);
            Manifest=Json.Deserialize<Manifest>(File.ReadAllText(Path.Combine(Package,"manifest.json")));
            if (Manifest==null || Manifest.format!=1 || Manifest.title_id!="NPJB00514" || Manifest.files==null || Manifest.files.Length!=3)
                throw new Exception("Unsupported patch manifest.");
            if (!Manifest.files.Select(f=>f.path).OrderBy(p=>p).SequenceEqual(Allowed.OrderBy(p=>p)))
                throw new Exception("Unexpected game files in manifest.");
            foreach (var f in Manifest.files)
            {
                Inside(Path.Combine(Game,"USRDIR"),f.path); Inside(Package,f.patch);
                if (f.target_size<1 || f.target_size>512*1024*1024 || f.decrypt!=(f.path=="EBOOT.BIN")) throw new Exception("Invalid patch entry.");
            }
        }
        string Destination(PatchFile f) { return Inside(Path.Combine(Game,"USRDIR"),f.path); }
        string Backup(PatchFile f) { return Inside(Path.Combine(Data,"backups"),f.path); }
        State ReadState() { return File.Exists(StatePath)?Json.Deserialize<State>(File.ReadAllText(StatePath)):new State(); }
        void WriteState(State state)
        {
            var tmp=StatePath+".tmp"; File.WriteAllText(tmp,Json.Serialize(state));
            if (File.Exists(StatePath)) File.Replace(tmp,StatePath,null); else File.Move(tmp,StatePath);
        }
        public void Check()
        {
            var state=ReadState();
            foreach (var f in Manifest.files)
            {
                if (HashFile(Inside(Package,f.patch))!=f.patch_sha256) throw new Exception("Damaged patch payload: "+f.path);
                var current=HashFile(Destination(f));
                if (current==f.target_sha256) { Log("Already translated: "+f.path); continue; }
                if (current==f.original_sha256 || (f.decrypt && current==f.source_sha256)) { Log("Supported original: "+f.path); continue; }
                string previous;
                if (((state.installed!=null && state.installed.TryGetValue(f.path,out previous) && current==previous) ||
                     (state.previous!=null && state.previous.TryGetValue(f.path,out previous) && current==previous)) && File.Exists(Backup(f)) &&
                    (HashFile(Backup(f))==f.original_sha256 || (f.decrypt && HashFile(Backup(f))==f.source_sha256)))
                { Log("Supported upgrade: "+f.path); continue; }
                throw new Exception("Unsupported or modified file: "+f.path+"\r\nSHA-256: "+current+"\r\nUse a clean supported game install or restore its original files first.");
            }
        }
        public static byte[] Apply(byte[] source, byte[] patch, long expectedSize)
        {
            using (var stream=new DeflateStream(new MemoryStream(patch),CompressionMode.Decompress))
            using (var r=new BinaryReader(stream))
            using (var output=new MemoryStream())
            {
                if (Encoding.ASCII.GetString(r.ReadBytes(8))!="SRWDIF01" || r.ReadInt64()!=expectedSize) throw new Exception("Invalid patch header.");
                while (true)
                {
                    int op=r.ReadByte(); if (op=='E') break;
                    if (op=='C')
                    {
                        uint off=r.ReadUInt32(), n=r.ReadUInt32();
                        if ((long)off+n>source.Length || output.Length+n>expectedSize) throw new Exception("Invalid patch copy.");
                        output.Write(source,(int)off,(int)n);
                    }
                    else if (op=='A')
                    {
                        uint n=r.ReadUInt32();
                        if (output.Length+n>expectedSize) throw new Exception("Invalid patch literal.");
                        var data=r.ReadBytes((int)n); if (data.Length!=n) throw new Exception("Truncated patch.");
                        output.Write(data,0,data.Length);
                    }
                    else throw new Exception("Invalid patch command.");
                }
                if (output.Length!=expectedSize || stream.ReadByte()!=-1) throw new Exception("Patch output length mismatch.");
                return output.ToArray();
            }
        }
        static void ClosedEmulator()
        { if (Process.GetProcessesByName("rpcs3").Length!=0) throw new Exception("Close RPCS3 before installing or restoring the patch."); }
        byte[] Source(PatchFile f, string baseline, string stage, string rpcs3, string elf)
        {
            var bytes=File.ReadAllBytes(baseline);
            if (Hash(bytes)==f.source_sha256) return bytes;
            if (!f.decrypt) throw new Exception("Original source hash mismatch: "+f.path);
            if (!String.IsNullOrWhiteSpace(elf))
            {
                bytes=File.ReadAllBytes(elf);
                if (Hash(bytes)!=f.source_sha256) throw new Exception("The selected decrypted ELF is not the supported original version.");
                return bytes;
            }
            if (String.IsNullOrWhiteSpace(rpcs3) || !File.Exists(rpcs3) || !String.Equals(Path.GetFileName(rpcs3),"rpcs3.exe",StringComparison.OrdinalIgnoreCase))
                throw new Exception("Select your rpcs3.exe, or provide the original decrypted EBOOT.elf in the optional field.");
            var input=Path.Combine(stage,"EBOOT.BIN"); File.WriteAllBytes(input,bytes);
            Log("Decrypting a temporary copy with your RPCS3...");
            var info=new ProcessStartInfo(Path.GetFullPath(rpcs3),"--decrypt \""+input+"\"") {
                WorkingDirectory=Path.GetDirectoryName(Path.GetFullPath(rpcs3)),UseShellExecute=false,
                CreateNoWindow=true,WindowStyle=ProcessWindowStyle.Hidden,
                RedirectStandardInput=true,RedirectStandardOutput=true,RedirectStandardError=true };
            using (var process=Process.Start(info))
            {
                var stdout=process.StandardOutput.ReadToEndAsync(); var stderr=process.StandardError.ReadToEndAsync();
                process.StandardInput.Close();
                if (!process.WaitForExit(90000)) { process.Kill(); throw new Exception("RPCS3 decryption timed out. Try the optional decrypted ELF field."); }
                // Drain redirected output, but do not include license/key data in our log.
                stdout.Wait(); stderr.Wait();
            }
            var output=Path.ChangeExtension(input,"elf");
            if (!File.Exists(output) || HashFile(output)!=f.source_sha256)
                throw new Exception("RPCS3 did not produce the supported original ELF. Confirm the original game boots, or select its decrypted EBOOT.elf.");
            return File.ReadAllBytes(output);
        }
        void Commit(Dictionary<string,byte[]> replacements, State state, string stage)
        {
            var previous=new Dictionary<string,byte[]>(); var changed=new List<string>();
            foreach (var pair in replacements) previous[pair.Key]=File.ReadAllBytes(pair.Key);
            try
            {
                foreach (var pair in replacements)
                {
                    // Same-volume atomic replacement; stage is within this game folder.
                    var temp=Path.Combine(stage,Guid.NewGuid().ToString("N")+".new"); File.WriteAllBytes(temp,pair.Value);
                    if (HashFile(pair.Key)!=Hash(previous[pair.Key])) throw new Exception("A game file changed during installation.");
                    File.Replace(temp,pair.Key,null); changed.Add(pair.Key);
                    if (FaultAfter==changed.Count) throw new Exception("Injected commit failure.");
                }
                WriteState(state);
            }
            catch (Exception error)
            {
                var failures=new List<string>();
                foreach (var path in changed.AsEnumerable().Reverse())
                {
                    try { var tmp=Path.Combine(stage,Guid.NewGuid().ToString("N")+".rollback"); File.WriteAllBytes(tmp,previous[path]); File.Replace(tmp,path,null); }
                    catch { failures.Add(path); }
                }
                if (failures.Count!=0) throw new Exception("Installation failed; rollback could not restore: "+String.Join(", ",failures)+". Keep .srwt1-english and use Restore originals.",error);
                throw;
            }
        }
        public void Install(string rpcs3, string elf)
        {
            ClosedEmulator(); Check(); Directory.CreateDirectory(Data);
            using (var gate=new FileStream(Path.Combine(Data,"lock"),FileMode.OpenOrCreate,FileAccess.ReadWrite,FileShare.None))
            {
                Check();
                var stage=Path.Combine(Data,"staging-"+Guid.NewGuid().ToString("N")); Directory.CreateDirectory(stage);
                try
                {
                    var replacements=new Dictionary<string,byte[]>();
                    var old=ReadState();
                    foreach (var f in Manifest.files)
                    {
                        var dst=Destination(f); var current=HashFile(dst);
                        if (current==f.target_sha256) continue;
                        var baseline=dst;
                        if (File.Exists(Backup(f))) baseline=Backup(f);
                        var baselineHash=HashFile(baseline);
                        if (baselineHash!=f.original_sha256 && !(f.decrypt && baselineHash==f.source_sha256)) throw new Exception("Original backup does not match: "+f.path);
                        Log("Preparing "+f.path+"...");
                        var source=Source(f,baseline,stage,rpcs3,elf);
                        var translated=Apply(source,File.ReadAllBytes(Inside(Package,f.patch)),f.target_size);
                        if (Hash(translated)!=f.target_sha256) throw new Exception("Translated file failed verification: "+f.path);
                        replacements.Add(dst,translated);
                    }
                    if (replacements.Count==0)
                    {
                        if (Manifest.files.All(f=>File.Exists(Backup(f))))
                            WriteState(new State {version=Manifest.version,status="installed",installed=Manifest.files.ToDictionary(f=>f.path,f=>f.target_sha256)});
                        Log("This version is already installed."); return;
                    }
                    foreach (var f in Manifest.files)
                        if (!replacements.ContainsKey(Destination(f)) && !File.Exists(Backup(f)))
                            throw new Exception("An already translated file has no original backup: "+f.path+". Start from a clean game installation to enable complete restoration.");
                    // All outputs exist and verify before original backups or game files change.
                    foreach (var f in Manifest.files)
                    {
                        if (!replacements.ContainsKey(Destination(f))) continue;
                        if (!File.Exists(Backup(f))) { Directory.CreateDirectory(Path.GetDirectoryName(Backup(f))); File.Copy(Destination(f),Backup(f),false); }
                        var hash=HashFile(Backup(f));
                        if (hash!=f.original_sha256 && !(f.decrypt && hash==f.source_sha256)) throw new Exception("Backup verification failed: "+f.path);
                    }
                    var state=new State { version=Manifest.version,status="installing",installed=Manifest.files.ToDictionary(f=>f.path,f=>f.target_sha256),
                        previous=old.installed??new Dictionary<string,string>() };
                    if (old.status=="installing" && old.previous!=null)
                        foreach(var pair in old.previous)if(!state.previous.ContainsKey(pair.Key))state.previous[pair.Key]=pair.Value;
                    WriteState(state); // recovery record survives an interrupted multi-file commit
                    Commit(replacements,new State {version=Manifest.version,status="installed",installed=state.installed},stage);
                    Log("English patch "+Manifest.version+" installed. Start the game in RPCS3.");
                }
                finally { Directory.Delete(stage,true); }
            }
        }
        public void Restore()
        {
            ClosedEmulator();
            if (!Directory.Exists(Data)) throw new Exception("No patch backups were found for this game.");
            using (var gate=new FileStream(Path.Combine(Data,"lock"),FileMode.OpenOrCreate,FileAccess.ReadWrite,FileShare.None))
            {
                var state=ReadState(); var replacements=new Dictionary<string,byte[]>();
                foreach (var f in Manifest.files)
                {
                    if (!File.Exists(Backup(f)))
                    {
                        var hash=HashFile(Destination(f));
                        if (hash==f.original_sha256 || (f.decrypt && hash==f.source_sha256)) continue;
                        throw new Exception("Original backup missing: "+f.path);
                    }
                    var bytes=File.ReadAllBytes(Backup(f)); var original=Hash(bytes); var current=HashFile(Destination(f)); string installed;
                    if (original!=f.original_sha256 && !(f.decrypt && original==f.source_sha256)) throw new Exception("Original backup is damaged: "+f.path);
                    if (current!=original && current!=f.target_sha256 &&
                        !(state.installed!=null && state.installed.TryGetValue(f.path,out installed) && current==installed) &&
                        !(state.previous!=null && state.previous.TryGetValue(f.path,out installed) && current==installed))
                        throw new Exception("Refusing to overwrite a later modification: "+f.path);
                    if (current!=original) replacements.Add(Destination(f),bytes);
                }
                var stage=Path.Combine(Data,"staging-"+Guid.NewGuid().ToString("N")); Directory.CreateDirectory(stage);
                try { Commit(replacements,new State {version=Manifest.version,status="restored"},stage); }
                finally { Directory.Delete(stage,true); }
                Log("Original game files restored. Backups retained.");
            }
        }
    }

    public sealed class Window : Form
    {
        readonly TextBox game=new TextBox(), rpc=new TextBox(), elf=new TextBox(), log=new TextBox();
        readonly Button check=new Button(), install=new Button(), restore=new Button();
        readonly List<Button> browse=new List<Button>();
        bool busy;
        readonly string package;
        public Window(string package)
        {
            this.package=package; Text="Super Robot Wars HD - English Patcher"; ClientSize=new Size(760,490);
            Font=new Font("Segoe UI",10); FormBorderStyle=FormBorderStyle.FixedDialog; MaximizeBox=false;
            StartPosition=FormStartPosition.CenterScreen;
            Controls.Add(new Label {Text="Install the English translation for NPJB00514",Font=new Font(Font,FontStyle.Bold),AutoSize=true,Location=new Point(20,18)});
            Controls.Add(new Label {Text="Close RPCS3 before patching. Originals are backed up for restoration.",AutoSize=true,Location=new Point(20,48)});
            Row("RPCS3 executable",rpc,82,false,"RPCS3|rpcs3.exe");
            Row("Installed game folder",game,145,true,"");
            Row("Decrypted ELF (optional)",elf,208,false,"Decrypted executable|*.elf|All files|*.*");
            log.SetBounds(20,278,720,142); log.Multiline=true; log.ReadOnly=true; log.ScrollBars=ScrollBars.Vertical; Controls.Add(log);
            check.Text="Check files"; install.Text="Install English patch"; restore.Text="Restore originals";
            check.SetBounds(20,438,140,34); install.SetBounds(330,438,200,34); restore.SetBounds(545,438,195,34);
            Controls.AddRange(new Control[]{check,install,restore});
            check.Click+=delegate {Run("check");}; install.Click+=delegate {Run("install");}; restore.Click+=delegate {Run("restore");};
            FormClosing+=delegate(object sender,FormClosingEventArgs e) {if(busy)e.Cancel=true;};
            foreach(var candidate in new[]{Path.Combine(package,"rpcs3.exe"),Path.GetFullPath(Path.Combine(package,"..","rpcs3.exe"))})
                if(File.Exists(candidate)){rpc.Text=candidate;SuggestGame();break;}
            Append("Preview release. Select your RPCS3 executable and installed game folder, then click Install.");
        }
        void Row(string title,TextBox box,int y,bool folder,string filter)
        {
            Controls.Add(new Label {Text=title,AutoSize=true,Location=new Point(20,y)});
            box.SetBounds(20,y+23,610,27); Controls.Add(box);
            var button=new Button {Text="Browse..."}; button.SetBounds(640,y+21,100,30); Controls.Add(button); browse.Add(button);
            button.Click+=delegate {
                if(folder) {using(var dialog=new FolderBrowserDialog {Description="Choose NPJB00514 or your RPCS3 folder"}) if(dialog.ShowDialog()==DialogResult.OK)box.Text=dialog.SelectedPath;}
                else {using(var dialog=new OpenFileDialog {Filter=filter}) if(dialog.ShowDialog()==DialogResult.OK)box.Text=dialog.FileName;}
                if(box==rpc)SuggestGame();
            };
        }
        void SuggestGame() {try {game.Text=Core.ResolveGame(Path.GetDirectoryName(rpc.Text));} catch {} }
        void Append(string line) { if(InvokeRequired){BeginInvoke(new Action<string>(Append),line);return;} log.AppendText(line+Environment.NewLine); }
        void Run(string action)
        {
            string selectedGame=game.Text, selectedRpc=rpc.Text, selectedElf=elf.Text;
            busy=true; check.Enabled=install.Enabled=restore.Enabled=false;
            game.Enabled=rpc.Enabled=elf.Enabled=false; foreach(var b in browse)b.Enabled=false;
            var worker=new BackgroundWorker();
            worker.DoWork+=delegate {Program.Execute(package,selectedGame,selectedRpc,selectedElf,action,Append);};
            worker.RunWorkerCompleted+=delegate(object sender,RunWorkerCompletedEventArgs e) {
                busy=false; check.Enabled=install.Enabled=restore.Enabled=true; game.Enabled=rpc.Enabled=elf.Enabled=true;foreach(var b in browse)b.Enabled=true;
                if(e.Error!=null)Append("Stopped: "+e.Error.Message);
            };
            worker.RunWorkerAsync();
        }
    }
    public static class Program
    {
        public static void Execute(string package,string game,string rpc,string elf,string action,Action<string> log)
        {
            var core=new Core(package,game); var lines=new List<string>();
            core.Log=delegate(string message){lines.Add(message);log(message);};
            try {if(action=="check"){core.Check();core.Log("File checks passed.");}else if(action=="restore")core.Restore();else core.Install(rpc,elf);}
            catch(Exception e){lines.Add("Stopped: "+e.Message);throw;}
            finally {if(action!="check")try {var data=Path.Combine(core.Game,".srwt1-english");Directory.CreateDirectory(data);File.AppendAllLines(Path.Combine(data,"install.log"),new[]{DateTime.UtcNow.ToString("o")+" "+action}.Concat(lines));}catch {} }
        }
        [STAThread] public static int Main(string[] args)
        {
            var package=AppDomain.CurrentDomain.BaseDirectory;
            if(args.Length==0){Application.EnableVisualStyles();Application.SetCompatibleTextRenderingDefault(false);Application.Run(new Window(package));return 0;}
            try
            {
                var options=new Dictionary<string,string>(); string action=null;
                for(int i=0;i<args.Length;i++)
                {
                    if(new[]{"--check","--install","--restore"}.Contains(args[i])) {if(action!=null)throw new Exception("Choose one action.");action=args[i].Substring(2);}
                    else if(new[]{"--game","--rpcs3","--elf"}.Contains(args[i]) && i+1<args.Length)options[args[i]]=args[++i];
                    else throw new Exception("Unknown or incomplete argument: "+args[i]);
                }
                if(action==null || !options.ContainsKey("--game"))throw new Exception("Use --check, --install or --restore with --game PATH.");
                Execute(package,options["--game"],options.ContainsKey("--rpcs3")?options["--rpcs3"]:null,options.ContainsKey("--elf")?options["--elf"]:null,action,Console.WriteLine);
                return 0;
            }
            catch(Exception e){Console.Error.WriteLine(e.Message);return 1;}
        }
    }
}
