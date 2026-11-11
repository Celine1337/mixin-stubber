#!/usr/bin/env python3
"""mixin-stubber — generate SpongePowered Mixin stubs from vanilla Minecraft
method signatures. Stdlib only, Python 3.9+.

Accepts:
  Lnet/minecraft/client/Minecraft;->runTick()V      (ASM)
  net.minecraft.client.Minecraft#runTick()V         (hash + JVM descriptor)
  net.minecraft.client.Minecraft.runTick(boolean)   (readable)
  boolean net.minecraft...#someMethod(int)          (return-first)
  net.minecraft.class_310#method_1523               (intermediary/SRG, bare)
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass

__version__ = "1.0.0"

JVM_PRIM = {"V": "void", "Z": "boolean", "B": "byte", "C": "char", "S": "short",
            "I": "int", "J": "long", "F": "float", "D": "double"}
JAVA_PRIM = {v: k for k, v in JVM_PRIM.items()}
BOXED = {"boolean": "Boolean", "byte": "Byte", "char": "Character", "short": "Short",
         "int": "Integer", "long": "Long", "float": "Float", "double": "Double"}
DEFAULTS = {"boolean": "false", "byte": "0", "char": "'\\u0000'", "short": "0",
            "int": "0", "long": "0L", "float": "0.0F", "double": "0.0"}
JAVA_LANG = {"String", "Object", "Integer", "Boolean", "Byte", "Character", "Short",
             "Long", "Float", "Double", "Number", "CharSequence", "Runnable", "Thread",
             "Class", "Enum", "Iterable", "Comparable", "StringBuilder", "StringBuffer",
             "Math", "System", "Exception", "RuntimeException", "Throwable", "Error",
             "Override", "Deprecated", "SuppressWarnings", "FunctionalInterface"}

MIXIN_IMPORTS = {
    "Mixin": "org.spongepowered.asm.mixin.Mixin",
    "At": "org.spongepowered.asm.mixin.injection.At",
    "Inject": "org.spongepowered.asm.mixin.injection.Inject",
    "Redirect": "org.spongepowered.asm.mixin.injection.Redirect",
    "CallbackInfo": "org.spongepowered.asm.mixin.injection.callback.CallbackInfo",
    "CallbackInfoReturnable": "org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable",
}


class SigError(ValueError):
    pass


@dataclass
class MethodSig:
    cls: str                 # fully qualified, dot-separated
    name: str
    args: list               # Java type strings
    ret: str | None          # Java type or None if unknown
    descriptor: str | None   # JVM "(args)ret" when known
    args_known: bool


# ---------------------------------------------------------------- parsing

def parse_jvm_type(s: str, i: int = 0):
    arr = 0
    while i < len(s) and s[i] == "[":
        arr += 1
        i += 1
    if i >= len(s):
        raise SigError("truncated JVM type")
    c = s[i]
    if c == "L":
        j = s.find(";", i)
        if j < 0:
            raise SigError("unterminated L type in descriptor")
        t = s[i + 1:j].replace("/", ".")
        i = j + 1
    elif c in JVM_PRIM:
        t = JVM_PRIM[c]
        i += 1
    else:
        raise SigError(f"bad JVM type code: {c!r}")
    return t + "[]" * arr, i


def parse_jvm_args(inner: str) -> list:
    out, i = [], 0
    while i < len(inner):
        t, i = parse_jvm_type(inner, i)
        out.append(t)
    return out


def is_jvm_args(inner: str) -> bool:
    if not inner:
        return True
    if "," in inner or " " in inner or "<" in inner:
        return False
    try:
        parse_jvm_args(inner)
        return True
    except SigError:
        return False


def java_to_jvm(t: str) -> str:
    t = re.sub(r"<.*>", "", t).strip()
    arr = ""
    while t.endswith("[]"):
        arr += "["
        t = t[:-2]
    if t in JAVA_PRIM:
        return arr + JAVA_PRIM[t]
    if "." not in t:
        raise SigError(f"cannot build descriptor: unknown package for {t!r}")
    return arr + "L" + t.replace(".", "/") + ";"


def split_types(s: str) -> list:
    parts, depth, cur = [], 0, ""
    for ch in s:
        if ch == "<":
            depth += 1
        elif ch == ">":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append(cur.strip())
            cur = ""
        else:
            cur += ch
    if cur.strip():
        parts.append(cur.strip())
    return parts


def parse_signature(text: str) -> MethodSig:
    s = text.strip()
    if not s:
        raise SigError("empty signature")

    ret_prefix = None
    m = re.match(r"^L([^;]+);->(.+)$", s)
    if m:
        cls, rest = m.group(1).replace("/", "."), m.group(2)
    else:
        parts = s.split(None, 1)
        if len(parts) == 2:
            first, remainder = parts
            base = first.split("<")[0].replace("[]", "")
            looks_like_type = "(" not in first and "#" not in first
            if looks_like_type and (base in JAVA_PRIM or "<" in first or first.endswith("[]")
                    or (("." in first or first[0].isupper())
                        and ("#" in remainder or "." in remainder))):
                ret_prefix, s = first, remainder
        if "#" in s:
            cls, rest = s.split("#", 1)
        else:
            paren = s.find("(")
            head = s[:paren] if paren >= 0 else s
            dot = head.rfind(".")
            if dot < 0:
                raise SigError("class must be fully qualified, e.g. net.minecraft.world.entity.player.Player#tick()V")
            cls = head[:dot]
            rest = head[dot + 1:] + (s[paren:] if paren >= 0 else "")

    cls = cls.strip().replace("/", ".")
    if not re.fullmatch(r"[A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)+", cls):
        raise SigError(f"bad class name: {cls!r}")

    rest = rest.strip()
    paren = rest.find("(")
    if paren < 0:
        name, inner, ret = rest, None, ret_prefix
    else:
        name = rest[:paren].strip()
        close = rest.rfind(")")
        if close < paren:
            raise SigError("unbalanced parentheses in signature")
        inner = rest[paren + 1:close].strip()
        after = rest[close + 1:].strip()
        if after.startswith(":"):
            after = after[1:].strip()
        ret = after or ret_prefix

    if not re.fullmatch(r"[A-Za-z_$][\w$]*|<init>|<clinit>", name):
        raise SigError(f"bad method name: {name!r}")

    args, descriptor = [], None
    if inner is not None:
        if is_jvm_args(inner):
            args = parse_jvm_args(inner)
            if ret:
                try:
                    jret, _ = parse_jvm_type(ret)
                    descriptor, ret = "(" + inner + ")" + ret, jret
                except SigError:
                    try:
                        descriptor = "(" + inner + ")" + java_to_jvm(ret)
                    except SigError:
                        descriptor = None
        else:
            args = split_types(inner)
            for a in args:
                if not re.fullmatch(r"[A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*(?:<.*>)?(?:\[\])*", a):
                    raise SigError(f"bad argument type: {a!r}")
            if ret:
                try:
                    descriptor = "(" + "".join(java_to_jvm(a) for a in args) + ")" + java_to_jvm(ret)
                except SigError:
                    descriptor = None
    if name in ("<init>", "<clinit>"):
        ret = "void"

    return MethodSig(cls=cls, name=name, args=args, ret=ret,
                     descriptor=descriptor, args_known=inner is not None)


def target_descriptor(sig: MethodSig) -> str:
    desc = sig.descriptor
    if desc is None:
        if not sig.args_known:
            raise SigError("INVOKE/redirect target needs a descriptor, e.g. Lpkg/Cls;->m(I)V")
        desc = "(" + "".join(java_to_jvm(a) for a in sig.args) + ")" + java_to_jvm(sig.ret or "void")
    return "L" + sig.cls.replace(".", "/") + ";->" + sig.name + desc


# ---------------------------------------------------------------- naming

def pascal(name: str) -> str:
    if name == "<init>":
        return "Init"
    if name == "<clinit>":
        return "Clinit"
    return "".join(p[:1].upper() + p[1:] for p in name.split("_") if p)


def decap(name: str) -> str:
    return name[:1].lower() + name[1:] if name else name


def simple_name(t: str) -> str:
    t = re.sub(r"<.*>", "", t).replace("[]", "")
    return t.rsplit(".", 1)[-1]


def boxed(t: str) -> str:
    base = simple_name(t)
    return BOXED.get(base, base)


# ---------------------------------------------------------------- generation

class Gen:
    def __init__(self):
        self.imports = set()
        self.unknown = set()

    def use(self, t: str) -> str:
        """Register imports for a Java type, return its source form (simple names)."""
        def repl(m):
            fqn = m.group(0)
            if fqn.startswith("java.lang."):
                return fqn.rsplit(".", 1)[-1]
            self.imports.add(fqn)
            return fqn.rsplit(".", 1)[-1]

        out = re.sub(r"[A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)+", repl, t)
        for word in re.findall(r"\b[A-Z][\w$]*\b", out):
            if word not in JAVA_LANG and word not in BOXED.values() and word not in self.unknown:
                if not any(i.rsplit(".", 1)[-1] == word for i in self.imports):
                    self.unknown.add(word)
        return out


def method_string(sig: MethodSig) -> str:
    return sig.name + sig.descriptor if sig.descriptor else sig.name


def generate(sig: MethodSig, opts) -> str:
    g = Gen()
    target_cls = g.use(sig.cls)
    mixin_cls = opts.name or target_cls + "Mixin"

    redirect = opts.mode == "redirect"
    at = "INVOKE" if redirect else opts.at
    target_sig = None
    if at == "INVOKE":
        if not opts.target:
            raise SigError("--target is required for INVOKE / redirect "
                           '(e.g. --target "Lpkg/Cls;->m(I)V")')
        target_sig = parse_signature(opts.target)
        if target_sig.ret is None:
            raise SigError("INVOKE/redirect target needs a return type, "
                           'e.g. "int pkg.Cls#m(int)" or Lpkg/Cls;->m(I)I')
        target_desc = target_descriptor(target_sig)

    cancellable = opts.cancellable or (at == "RETURN" and sig.ret not in (None, "void"))

    # ---- annotation
    method = method_string(sig)
    if at == "INVOKE":
        at_expr = f'@At(value = "INVOKE", target = "{target_desc}")'
    else:
        at_expr = f'@At("{at}")'
    ann = "Redirect" if redirect else "Inject"
    ann_args = [f'method = "{method}"', f"at = {at_expr}"]
    if not redirect and cancellable:
        ann_args.append("cancellable = true")
    if len(ann_args) == 2 and at != "INVOKE":
        annotation = f"@{ann}({', '.join(ann_args)})"
    else:
        annotation = f"@{ann}(\n        " + ",\n        ".join(ann_args) + "\n    )"

    # ---- handler signature
    static = "static " if opts.static else ""
    if redirect:
        ret_t = g.use(target_sig.ret or "void")
        params = []
        if not opts.target_static:
            recv = decap(simple_name(target_sig.cls))
            if any(recv == f"arg{i}" for i in range(len(target_sig.args))):
                recv = "instance"
            params.append(f"{g.use(target_sig.cls)} {recv}")
        params += [f"{g.use(a)} arg{i}" for i, a in enumerate(target_sig.args)]
        handler = f"redirect{pascal(target_sig.name)}"
        call_args = ", ".join(f"arg{i}" for i in range(len(target_sig.args)))
        if opts.target_static:
            call = f"{g.use(target_sig.cls)}.{target_sig.name}({call_args})"
        else:
            call = f"{recv}.{target_sig.name}({call_args})"
        body = [f"// TODO: replace call to {simple_name(target_sig.cls)}#{target_sig.name} (default: passthrough)"]
        body.append(("return " + call + ";") if ret_t != "void" else (call + ";"))
        handler_ret = ret_t
    else:
        params = [f"{g.use(a)} arg{i}" for i, a in enumerate(sig.args)]
        if sig.ret in (None, "void"):
            cb, cbvar = "CallbackInfo", "ci"
        else:
            cb, cbvar = f"CallbackInfoReturnable<{boxed(g.use(sig.ret))}>", "cir"
        params.append(f"{cb} {cbvar}")
        handler = f"on{pascal(sig.name)}{pascal(at.lower())}"
        handler_ret = "void"
        where = f"{simple_name(sig.cls)}#{method}"
        body = [f"// TODO: injected at {at} of {where}"]
        if cancellable:
            if cbvar == "ci":
                body.append("// ci.cancel();")
            else:
                d = DEFAULTS.get(simple_name(sig.ret or ""), "null")
                body.append(f"// cir.setReturnValue({d});")

    for name in (ann, "At", "Mixin", "CallbackInfo", "CallbackInfoReturnable"):
        g.imports.add(MIXIN_IMPORTS[name])
    if redirect:
        g.imports.discard(MIXIN_IMPORTS["CallbackInfo"])
        g.imports.discard(MIXIN_IMPORTS["CallbackInfoReturnable"])
        g.imports.discard(MIXIN_IMPORTS["Inject"])
    else:
        g.imports.discard(MIXIN_IMPORTS["Redirect"])
        if sig.ret in (None, "void"):
            g.imports.discard(MIXIN_IMPORTS["CallbackInfoReturnable"])
        else:
            g.imports.discard(MIXIN_IMPORTS["CallbackInfo"])

    # ---- assemble
    lines = [f"package {opts.package};", ""]
    ordered = [sig.cls] + sorted(i for i in g.imports if i != sig.cls and not i.startswith("java.lang."))
    for imp in ordered:
        lines.append(f"import {imp};")
    if g.unknown:
        lines.append("")
        lines.append("// TODO: add imports for: " + ", ".join(sorted(g.unknown)))
    lines += ["", f"@Mixin({target_cls}.class)", f"public abstract class {mixin_cls} {{", ""]
    if not sig.args_known:
        lines.append("    // NOTE: no descriptor given - add one if the target method is overloaded")
    lines.append("    " + annotation)
    lines.append(f"    private {static}{handler_ret} {handler}({', '.join(params)}) {{")
    lines += ["        " + b for b in body]
    lines += ["    }", "}", ""]
    return "\n".join(lines)


# ---------------------------------------------------------------- CLI

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="mixin-stubber",
        description="Generate a ready @Mixin class from a vanilla Minecraft method signature.",
        epilog='example: mixin-stubber "net.minecraft.world.entity.player.Player#tick()V" --at HEAD')
    p.add_argument("signature", nargs="?", help="target method signature (see README for formats)")
    p.add_argument("--mode", choices=["inject", "redirect"], default="inject")
    p.add_argument("--at", choices=["HEAD", "TAIL", "RETURN", "INVOKE"], default="HEAD",
                   help="injection point (default HEAD)")
    p.add_argument("--target", help="INVOKE/redirect target, e.g. Lpkg/Cls;->m(I)V")
    p.add_argument("--target-static", action="store_true", help="redirect target is static")
    p.add_argument("--static", action="store_true", help="target method is static (static handler)")
    p.add_argument("--cancellable", action="store_true", help="set cancellable = true")
    p.add_argument("--package", default="com.example.mixin", help="mixin package (default com.example.mixin)")
    p.add_argument("--name", help="mixin class name (default <Target>Mixin)")
    p.add_argument("--out", help="write to file instead of stdout")
    p.add_argument("--force", action="store_true", help="overwrite --out file")
    p.add_argument("--version", action="version", version=f"mixin-stubber {__version__}")
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    sig_text = args.signature
    if not sig_text:
        if sys.stdin.isatty():
            try:
                sig_text = input("signature> ").strip()
            except (EOFError, KeyboardInterrupt):
                print(file=sys.stderr)
                return 2
        else:
            build_parser().print_usage(sys.stderr)
            return 2
    try:
        sig = parse_signature(sig_text)
        code = generate(sig, args)
    except SigError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    if args.out:
        if os.path.exists(args.out) and not args.force:
            print(f"error: {args.out} exists (use --force)", file=sys.stderr)
            return 1
        parent = os.path.dirname(os.path.abspath(args.out))
        os.makedirs(parent, exist_ok=True)
        with open(args.out, "w", encoding="utf-8", newline="\n") as f:
            f.write(code)
        print(f"wrote {args.out}", file=sys.stderr)
    else:
        sys.stdout.write(code)
    return 0


if __name__ == "__main__":
    sys.exit(main())