#!/usr/bin/env python3
"""Tests for mixin-stubber. Run: python -m unittest discover -s tests -v"""
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import mixin_stubber as ms

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "mixin_stubber.py")


def gen(sig, *argv):
    opts = ms.build_parser().parse_args([sig, *argv])
    return ms.generate(ms.parse_signature(sig), opts)


class TestParsing(unittest.TestCase):
    def test_asm_form(self):
        s = ms.parse_signature("Lnet/minecraft/client/Minecraft;->runTick()V")
        self.assertEqual(s.cls, "net.minecraft.client.Minecraft")
        self.assertEqual(s.name, "runTick")
        self.assertEqual(s.args, [])
        self.assertEqual(s.ret, "void")
        self.assertEqual(s.descriptor, "()V")

    def test_hash_descriptor(self):
        s = ms.parse_signature("net.minecraft.world.entity.player.Player#hurt(Lnet/minecraft/world/damagesource/DamageSource;F)Z")
        self.assertEqual(s.name, "hurt")
        self.assertEqual(s.args, ["net.minecraft.world.damagesource.DamageSource", "float"])
        self.assertEqual(s.ret, "boolean")
        self.assertEqual(s.descriptor, "(Lnet/minecraft/world/damagesource/DamageSource;F)Z")

    def test_dot_readable(self):
        s = ms.parse_signature("net.minecraft.util.Mth.clamp(int, int, int)")
        self.assertEqual(s.cls, "net.minecraft.util.Mth")
        self.assertEqual(s.name, "clamp")
        self.assertEqual(s.args, ["int", "int", "int"])
        self.assertIsNone(s.ret)

    def test_return_first(self):
        s = ms.parse_signature("boolean net.minecraft.world.entity.player.Player#isSleeping()")
        self.assertEqual(s.ret, "boolean")
        self.assertEqual(s.name, "isSleeping")
        self.assertEqual(s.descriptor, "()Z")

    def test_return_first_qualified(self):
        s = ms.parse_signature("net.minecraft.world.food.FoodData net.minecraft.world.entity.player.Player#getFoodData()")
        self.assertEqual(s.ret, "net.minecraft.world.food.FoodData")
        self.assertEqual(s.descriptor, "()Lnet/minecraft/world/food/FoodData;")

    def test_colon_return(self):
        s = ms.parse_signature("net.minecraft.util.Mth#clamp(int, int, int): int")
        self.assertEqual(s.ret, "int")
        self.assertEqual(s.descriptor, "(III)I")

    def test_bare_intermediary(self):
        s = ms.parse_signature("net.minecraft.class_310#method_1523")
        self.assertEqual(s.name, "method_1523")
        self.assertFalse(s.args_known)
        self.assertIsNone(s.descriptor)

    def test_generics_split(self):
        s = ms.parse_signature("com.example.Foo#bar(java.util.List<String>, java.util.Map<String, Integer>, int)")
        self.assertEqual(s.args, ["java.util.List<String>", "java.util.Map<String, Integer>", "int"])

    def test_arrays(self):
        s = ms.parse_signature("com.example.Foo#bar([[ILjava/lang/String;[Ljava/lang/Object;)V")
        self.assertEqual(s.args, ["int[][]", "java.lang.String", "java.lang.Object[]"])

    def test_constructor(self):
        s = ms.parse_signature("net.minecraft.world.entity.player.Player#<init>(Lnet/minecraft/world/level/Level;)V")
        self.assertEqual(s.name, "<init>")
        self.assertEqual(s.ret, "void")

    def test_errors(self):
        for bad in ("", "   ", "NoPackage#m()V", "a.b.C#") :
            with self.assertRaises(ms.SigError, msg=bad):
                ms.parse_signature(bad)
        with self.assertRaises(ms.SigError):
            ms.parse_signature("a.b.C#m(I")
        with self.assertRaises(ms.SigError):
            ms.parse_signature("a.b.C#m(123)V")


class TestGenerate(unittest.TestCase):
    def test_inject_head_void(self):
        out = gen("net.minecraft.world.entity.player.Player#tick()V")
        self.assertIn('@Inject(method = "tick()V", at = @At("HEAD"))', out)
        self.assertIn("private void onTickHead(CallbackInfo ci)", out)
        self.assertIn("@Mixin(Player.class)", out)
        self.assertIn("public abstract class PlayerMixin", out)
        self.assertIn("import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;", out)
        self.assertNotIn("CallbackInfoReturnable", out)
        self.assertNotIn("cancellable", out)

    def test_inject_return_nonvoid(self):
        out = gen("net.minecraft.util.Mth#clamp(III)I", "--at", "RETURN")
        self.assertIn("CallbackInfoReturnable<Integer> cir", out)
        self.assertIn("cancellable = true", out)
        self.assertIn("// cir.setReturnValue(0);", out)

    def test_inject_target_args(self):
        out = gen("a.b.C#hurt(Lx/y/DamageSource;F)Z")
        self.assertIn("private void onHurtHead(DamageSource arg0, float arg1, CallbackInfoReturnable<Boolean> cir)", out)
        self.assertIn("import x.y.DamageSource;", out)

    def test_cancellable_head(self):
        out = gen("a.b.C#tick()V", "--cancellable")
        self.assertIn("cancellable = true", out)
        self.assertIn("// ci.cancel();", out)

    def test_static_handler(self):
        out = gen("a.b.C#tick()V", "--static")
        self.assertIn("private static void onTickHead", out)

    def test_redirect_instance(self):
        out = gen("Lnet/minecraft/client/Minecraft;->runTick()V", "--mode", "redirect",
                  "--target", "Lnet/minecraft/client/gui/Gui;->render(Lnet/minecraft/client/gui/GuiGraphics;F)V")
        self.assertIn('@At(value = "INVOKE", target = "Lnet/minecraft/client/gui/Gui;->render(Lnet/minecraft/client/gui/GuiGraphics;F)V")', out)
        self.assertIn("private void redirectRender(Gui gui, GuiGraphics arg0, float arg1)", out)
        self.assertIn("gui.render(arg0, arg1);", out)
        self.assertIn("import org.spongepowered.asm.mixin.injection.Redirect;", out)
        self.assertNotIn("Inject", out.replace("injection", ""))

    def test_redirect_static(self):
        out = gen("a.b.C#run()V", "--mode", "redirect", "--target", "Lx/y/Util;->log(Ljava/lang/String;)V",
                  "--target-static")
        self.assertIn("private void redirectLog(String arg0)", out)
        self.assertIn("Util.log(arg0);", out)

    def test_redirect_nonvoid(self):
        out = gen("a.b.C#run()V", "--mode", "redirect", "--target", "Lx/y/Util;->calc(I)I")
        self.assertIn("private int redirectCalc(Util util, int arg0)", out)
        self.assertIn("return util.calc(arg0);", out)

    def test_redirect_return_first_target(self):
        out = gen("a.b.C#run()V", "--mode", "redirect", "--target", "int x.y.Util#calc(int)",
                  "--target-static")
        self.assertIn('target = "Lx/y/Util;->calc(I)I"', out)
        self.assertIn("private int redirectCalc(int arg0)", out)
        self.assertIn("return Util.calc(arg0);", out)

    def test_redirect_target_needs_return_type(self):
        with self.assertRaises(ms.SigError):
            gen("a.b.C#run()V", "--mode", "redirect", "--target", "x.y.Util#calc(int)")

    def test_inject_invoke(self):
        out = gen("a.b.C#run()V", "--at", "INVOKE", "--target", "Lx/y/Util;->log()V")
        self.assertIn('@At(value = "INVOKE", target = "Lx/y/Util;->log()V")', out)
        self.assertIn("CallbackInfo ci", out)

    def test_invoke_requires_target(self):
        with self.assertRaises(ms.SigError):
            gen("a.b.C#run()V", "--at", "INVOKE")
        with self.assertRaises(ms.SigError):
            gen("a.b.C#run()V", "--mode", "redirect")

    def test_constructor(self):
        out = gen("a.b.Player#<init>(Lx/y/Level;)V", "--at", "RETURN")
        self.assertIn('method = "<init>(Lx/y/Level;)V"', out)
        self.assertIn("onInitReturn(Level arg0, CallbackInfo ci)", out)

    def test_no_java_lang_import(self):
        out = gen("a.b.C#m(Ljava/lang/String;I)V")
        self.assertNotIn("import java.lang", out)
        self.assertIn("private void onMHead(String arg0, int arg1, CallbackInfo ci)", out)

    def test_unknown_imports_comment(self):
        out = gen("a.b.C#m(GuiGraphics, BlockPos)V")
        self.assertIn("// TODO: add imports for: BlockPos, GuiGraphics", out)

    def test_package_and_name(self):
        out = gen("a.b.C#m()V", "--package", "dev.test.mixins", "--name", "MyMixin")
        self.assertIn("package dev.test.mixins;", out)
        self.assertIn("public abstract class MyMixin", out)

    def test_bare_name_note(self):
        out = gen("net.minecraft.class_310#method_1523")
        self.assertIn('method = "method_1523"', out)
        self.assertIn("no descriptor given", out)


class TestCli(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, SCRIPT, *args], capture_output=True, text=True)

    def test_stdout(self):
        r = self.run_cli("a.b.C#m()V")
        self.assertEqual(r.returncode, 0)
        self.assertIn("@Mixin(C.class)", r.stdout)

    def test_out_file(self):
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "sub", "Dir", "CMixin.java")
            r = self.run_cli("a.b.C#m()V", "--out", out)
            self.assertEqual(r.returncode, 0)
            self.assertTrue(os.path.exists(out))
            with open(out, encoding="utf-8") as f:
                self.assertIn("@Mixin(C.class)", f.read())
            r2 = self.run_cli("a.b.C#m()V", "--out", out)
            self.assertEqual(r2.returncode, 1)
            r3 = self.run_cli("a.b.C#m()V", "--out", out, "--force")
            self.assertEqual(r3.returncode, 0)

    def test_bad_signature(self):
        r = self.run_cli("garbage")
        self.assertEqual(r.returncode, 1)
        self.assertIn("error:", r.stderr)

    def test_no_args(self):
        r = subprocess.run([sys.executable, SCRIPT], capture_output=True, text=True, stdin=subprocess.DEVNULL)
        self.assertEqual(r.returncode, 2)

    def test_version(self):
        r = self.run_cli("--version")
        self.assertEqual(r.returncode, 0)
        self.assertIn("mixin-stubber", r.stdout)


if __name__ == "__main__":
    unittest.main()