#!/usr/bin/env python3
"""Rebuild the exact 1029-variable modular system from the official prime list."""
from __future__ import annotations

import base64
import hashlib
import json
import math
import random
import time
import zlib
from pathlib import Path

from sympy import factorint, isprime, primitive_root

ROOT = Path(__file__).resolve().parent
EXPECTED_SHA256 = "fd7f67051b817842f5795fae812b852efa8007f5478a286365a7236a6a790cd8"
OFFICIAL_LIST_B85 = (
    'c-l3ZS(5BH3<Lk`G}@Q@U#v4Bcg)0VSCto;3jmVZXa8>5zgjq`ZQoxVlYh4VoW*zd-'
    'e2pd|Jp44v&R0lUGJ}V|5;qycfY^U_&5uf&COlr;k#8=|E<Nxy}1289Noedw~zk2UgjhDw^tre=k(w8p3N`6RyxP6dQO|0NB6S%z'
    'PIYb$K*DBRqox-<;+o5meRP-7+m%nv-$mQoHMTP!dvj`EG}@4>4N8BO{??!Z}A2H9$#b^SGD`%8=lP*_int=-'
    'pgOlY5jLf>%P>$HrIvnZkX(MSL4@vv_&l?hAp-'
    '8T`hNUlUirqxfdT^#~4~;j`)EE@ve0h%~n|lmtzYb+sg4~t*xSgdTU(XM%5IJ*YV4-J2z{KrTORF7N2z<+c3Iko-'
    'w@cVhv8YcolorqjNgvXxFh~-Z_0xzf+SBURSHKN?v%hrDukxYUHc!#$7&k*2_A66YKHPbIt9aQ#bd-Hlz7xU+%fu)v9Yu17cxqPd'
    'T~S?sXG{doIu9(0JIpuAv*6uenb`^vr%)(%H>GxV80_IGeg;RZVb-0-dsVi63-'
    '_Zs87kqV}n$YaPoNtNpCPW9lfk`FT`aXMXI&KYtA<{@&Az(OX))HpfY1PeX~nyn3!%r)tT12uZ_%OwhfpmSLh1($$!3wdK{D0W#v'
    '^ozH{ws(FAfJbx21O;^rq6cgd+-<hUny9DTbf8)=>S=gE1%1r*geCT*sZ*(2(=Sg@U^Qvzn4Leq!-'
    '_0Sf<K=SR9#wO8?eG0Bk@)^DUEo>C!@>i357M!C-'
    '?4hti(}oq*VyIU{2j61#2?+iW9N6wn02xGpu}8fnyEO8q!(#QFU8nu)6d{d@@!quz-%o-'
    'fZ5E#j3vUmB(z2|V)%QF143(v9xQ{5G}y+$^g%73zlmo7?3B7H=N+tK*q=%q^WLYmgx<m3+UcyG^&Nt@8JTwkMlTne@}@^M92-'
    'EGSlvfIa*wftAO@sSTS_&qK#{&aI9a9UfXquMH)7TpeqY=i9MjO?s#Cn-06%-5UDiyX6M(`wfyY8>LjS~vl~<g@Z-A7ZEWo%s_u-'
    '=p<e-DL20kQkdcL_efC`%R`f>x`^?b81rgXwfmzNHP{X1AJU*HGJS`IK!?z2q}ui6;HVB-'
    'LL)bNAPG>zKxPrW9p2~Y;_kqo*uKj9dHH9Uqb1QaZJ-cP_`tHDkHA(xK{w1#kI9r<RSvjUgI!U@72u+iWmg6__pFL$g-'
    'w@o&iCj!dtCfF)n`-HDnQjADRjsdQtC)w)GeLAsHrGgF+Hu0dJjhVgS-'
    'H#B6>)Kt9FT8aDnb>DpCK>2v)*8ftg8^d}S!m$u>eF$>5xU5@iFtW<Gi`+-'
    '0pu=N5IiTw9DoS!@tX^=mmF|A6FTqiouRq)=pRVdJ_MR{MN&@T@e#mUhV#V#2{zCkMRELwv@|0?#hujVW)C~D`qIA~@G_z@&?M(6'
    'E3mi9MY-'
    '@un+JumHf$VYa)4jVX)Ffgk<5sjkIyf@kxW=rPkt|>ne~v+C35IABGaXwzKD5qnaCQrg9G?%CadR*c|jFsCtoM87zyxzk^{nLJq6'
    'Gp*yyX$+xZd{gXQ%rPlF!c(fJaHBn6kvGQ!Da_+1-3GT(U@rAqb2p-K{UcC(Em-s418kX6L_Q+T9b=#O-'
    'Ka)~e<x6T|%w2@x~Wo<zlgaRh_X&&wO-6kZGecZH0@R)LS<}FcG+}O3iEMP*&@tC?vcL<04iO?e=q$0v{;VFM5YO#P<;4gwuYn-u'
    'aBp}qeF{bYU5+j+u{3mRMsH=oirH};E@bl<$%MslqJeM4?rmPCW($yhd?pOi{ybg~OBM7q<A<XNa_O2M!GzuM$$-'
    '+F3MXeeNhKpRYGMVd^Zwc)-{#UvRxS@8Tp(GxAGaJRjuD*>;JL@DhMFlkWko_fT?xG})^-'
    'knk7a&|c)Q#kb3|_~q4n32N*Bq2r@Ntuh+l@SvjJaBbS1g0pVh5`%@uf1dhg7jV4^$pN*XIV6K?@*XF&?4ge`J0UId)0_p5l8<l}'
    'dA^Q;v_Fr%7_8J)#r{4iF%ETO<a+%V}l+B#+$5U2qYnMm)B<KtPV}G-'
    'l0t2m^i;2C6sFABerW0>LOtmfr3=3K@VT$beU!;Gq=?TDPnb@ZTi!v+16DJ|Tt>P@8!K*isrODp)~J4yx4KJ0fj?l}G~CT3r1>=*'
    'k_+19W>)&>1yASTrlQ3w9j>2waJ5z#B8?k;L3j$w301l`Ad?w1n7eQkRl~103lq(4(Z#GpvG)o)3k(fU$+4A)O*Qz^U>fO;v1_2T'
    'mm9X^|S-vbd5631X*4I3VTtKk%hSZpkoEi@*$TV?|g*sa?GrHWLJ@Qe*~Ih&r-&<^*aD3Z`I^IW-'
    '~*2pK>mvVhePxHlq1Mc2M^5hSl!It<52HNpdOc(hpsy4fv?jQJyB2I5xvWCEeTZ%k8-'
    '{TC@<8?tK&?L@$^%!z7&qgoAIqMizgS0n6!r4tR$<5RnO2(FA$a)`9Vs+tcUk_D11XF_1-'
    '(=`}y1hh`4m@Pp|`Jg^QcP1ht1WXZ5f{dI%9io&iIV22L$sw;sj$0}ebD*48EppI4J%lNh1s0EQ<$g;x6DG<UTuSDc$Ia5Yr6zAm'
    'KmMCJBw51s9FpiMfMUE6dbUQv6%k$HE+J^c01dI~D@I7K8$rV%%c@F5I|^v8RwA}w`f+n#@CI=p1Cv<Cm`WK7WiD$oWLS|2vdC@m'
    '645~95&Gq%6e1@O)j}w-'
    'kElqy0EO5Ls2oxQ3h<z);&rvatu^E*!Pc!BQ5_S#U~m{!&{?5%l^f6~cUvHlx#XvZNTHLGyl=Vty#7d&Q(h6pTKHDb<^|5f6>t;f'
    'aq@`cx$!*KL*$-N0)iOSRNM?`fH0HlJp>&sPDiTAl6tD4Xii!htQ*svd`mpzB~2}_;sjMaM2)Mgvp6&Zk|G?S1d<{gnz`+M<-'
    'HP4QAm_-X;*z{9T*XMWyaFe1K{z%vRDlc75PO%h-'
    '{YKK~J<$nh4O|)bWvoSm&$uuJY=d{_`rtrg=dOKn8jFWzj<PO~GAqk1|Oq*2e>XUa|Ew8m7IVs$+@cW&xE#kz~Xh-'
    'T`|NzyipU$5tvd-awHgo`G9yCGa5zwZMFm5&53-18M-k>Q^XAohm2}MegHUST>qZR*tGR*6-'
    'mKkfm>x<WeUD<&U2v<twVa0KZZQKo?ZD2(9zMvI)~ubK780y9DT1{7fsuW5VNeo+_lDw`z_#o5H-'
    'jDiF*FVPjgt1~DoYk*XxllZ8HVx!fFYfbza$BW68-'
    'B~vHvh_FLjDAU{gKL$oqM5>i34T9KUhoPK4AjuATe`TepJo}TQwqw#!!feBkiHt_UPOIP`bW=k;xrx#CYgAZz@{wXC=ZG-'
    '4JpCDbp$LgQ)yOB5jeK2^(=*4AJ1?1Y5Fh7$eLAcI%7izOBmzL*kqV2joq2aMX!&BVewF(ZN)R7z5MTuNhOT>AS5=O9W<2~SySj~'
    '$Z~;Yhu_q!KpdEV8eF#Yxm~*bR`+fy+sI%L9)h*cNL~h?^I6pfmo)Ky(39jWkiM5|_rrc{OWMO)Ur9|v<C2K3`H5PM}-'
    '}1fQYAQ|WfU=_}p6yNoOnbiy8(*!Frl376-axHoosBU6s&KW!Yym^#3rOh#LZiwf61z4}=MrTlX22!JsTt?-'
    'w52lZE55IBqZC$w0EVfdAs6m<^dkm2dNr~dEdYR}Pl{PrF~U-*cctX(bCE-SPESja47sHbrruflLY;;_AQXBa9$W17^}@LQ>q<-'
    'V5?YRtVsVYNd(*~glMKbrdBp_35v~Mjf7Sdjdll@kg}|=jLe>?7SWFm36)%$xfyJ!g=sA!~Gb&T5TXhp?k?hlYS)FP(ym(Ez;VNo'
    'gSbpH?yb2kXe%w`3-'
    '~+|G>S2$34=aI*VFP=0lJ8BQ&IVV1!X6aDD&>K^kkBG_?cJ&9at`aXPcNpae{FiazTUDbnU57vp6&Hla25nW0HztxbmbK>ZE0yj{'
    'i4i;urqj|#>DB=0k#2@iR6Z`%CQJ>?6KJsw1V<Jr0mie=><}~qAymcz&1=xvlLLDYE-'
    '$0<E@Yl<{W!T>*Y0<PD{7QcVNP<pnXiD+RkwbE>qtQjJ74K@q^86ivhJR*=sq#&9=ZS72qgqulrhkr0nYF6Xw$zp$5^xVcY4&)(#'
    '(t8pi}V?TGdN-'
    '3H1qKqwl>7B{+*D&tWFPlG#ymuh<C)>E+6f}I2o>nMI~@CUBY^vB}6<pbDmtvjE%r`Gk<Z|;Mq+N<!@hUo6}>;Y?hInu|9E+?D5U'
    'gp3o=&IMISFV6@8FkbM$${JqfOnfSJ);Ib$n7YX*O@S#>Qn!`hr;2JADJQpJXRDNAnpgz#A2}<({s0L`>VcJuzp2!B|<=Z#FbJhq'
    '8?5LO<s9JT;m-A`?W2>sbix%(w?Ml%6hNaaASHsX=+@xTYXx8>g$u10BEhRd-'
    '`?)$EoA><9R&y2KFQWoquR~(Y^&tP0A<h@mF=8;|J1gS?kn@cnUO7JiqYobaEt(0PvQ|*gH**n&DHrFOmhQgMv`4BX^LVWV$o~qQ'
    'K7OiFdqiYdI=UI-25oS}VXcKS2o!W$~J|q>nE0)IfQL6gJ+#Im;Yec+9PtE(nS4D4;(f-'
    'Gz`<a|2{ldh0=PFmuTD<9z_^)G1;jIc4~#g$)=-'
    'u*6g&9gVv(#2d~f$7?C8v2hc^$#O(M#tHjfV^}Ixp3+_|og*D=$B^5f^m08*TA%5$UhIeNiR)R&k`B^&7TIy?e!Uac!)=9L(Rel+'
    'Ea{&K&Bq4ro0AZWcr+ph7dBxYr678ywAi5?BHSMIi6(I*Bd}ydNJI=H+eqaDXU%PKsABf1$t^x8u<U0?HN!{SkGjOBie=1G!yv^m'
    'B7(J10sy5TY@x|@H4{aW^kCso;g3~W9PE^0LWXvKt<;hk=S*Wp{zq%Q@|pl8@4>?8Gr}JJBCgU1D2b%{>8vs%7|MNTVqCn}W_lH('
    'UxDOW2CvFm(%>~xydLhvZ?C~&FgYuFGehgfJJPll^*UKF+q;gu!nnxDGv6l*Z-'
    'rla7*NOfSMoOW922#qJ%uw+dU|@=;;l$uGgGQDu%i?wOGJ-2L`fA?fgCAK;lL<!tf>1-X-_}OUM=;Rki!b0-'
    '^`Z{MpZmzz4vr#C{uNH1~7?fiHl4QEkeKomY%^$0Rwne$ppSB+m~f@S`Ss0K=6KJ81RM5PUfRcErcsqDy8Pe0<-'
    '1mL~|H4@AVD2A&_O4G-yT&AFGbN>Qk3?8P=PF8@f$e?3sfXNzv-s-'
    'z=6%jgc;Wlen>Bf0}d3zj!Z`L21&7#7Nt#DWx&y$=JTBYl~Beyb=BxhQ(95*2yDt+h|S+#1`&+(;yQP?>Yy!#WL(`wx=-'
    '7a#D1qFJR-'
    '?a0w1;@wLJ$YPrgzQQNPnG6Ij+G57;0%URpIqK$10Vgi_(0V47V`I~_qNet82E|_WiUZrV&=wZP)qz>fl8}Ve(8H`M;T4L-'
    '3xu?#xIFSJP)a)IWm7X7#%`7My2nBbYwa%8tIcs*3Fdk8@aJwy`RPx<awL}x=fg9juyDz|MT$ogwef4&gTV`e$=ri1>O-'
    '?qOz$sGsn;{*G8=JmSOPHX9&qFK7$t6$sO!l#Ru?8Vu9O$Gcfvib;q^6lp_^c0Lxc#!uS{X<1GQ-yB*JEttT<G|HMConq7%y0~HZ'
    '6%Jc!Lw$<tS^1FzGo0sTtlS)2Dj2iBaFw)b0oN=-'
    'EU<?&4{y(KlN`?to?3;bDde<AgAKH_ScvAS?minsnMObXNXKQ6wwz>J%hxM|)Exi-'
    '@?W7BmhS*0&dhcTY8)Uzd}%YweVFVasS*X`Y02v~A1yF}|u`&&(2DNw^GlC}Cy#%4()MI)zEIOywn^&}fe_-'
    '^<SSm5tuKT7{X@aCHH}SXW6g2ue@{rsPsjfGI^EgpQ3!?9QT6X*&FOXU*xaxU=`}7bAnGbOVPSpll_e%sMs`EgiGd!6<@GO2j|Nh'
    '*gmHHEmLRj)nCMyIm>e)ClK^vY%0thrR-NSbI==p0{_0>@MPlV>DA$%CcuL(@z^A@F2g^-3ieZOG-'
    ')B`7(qwubHxogmcazw^_9TyY|A!wzS2xi92ERQuZu>r$vcm>7kXb9h8<_xbw9p#w$EQoOW#69Or63a9QnZ=C9X=67odfy0U43Gsz'
    ';mPOH7@gZ~^wQ|X6vZ3nuq>dp6v1F~zXpx@pC0(YE<-q&o$KrU;)aj=$2Bcxc5-'
    'IoO0VJq@8tr)yo9q5$%b`*5`SWT)+W}l=nXxX2Rg<2en`jjZ%;k;wZr^880Ggw(4D}JP7$!0fJHLRvB4s0O#guAqG-AT0ji6F5R?'
    'VgBcj`XxAum<L{G;D8YfF*)WrOcU$GGV_v?0hq`Yi+vbSGK}T&2R8@%47^fs3UhVmSnmt35jb0E7J_(e;P5iKeK)2>d%oqBDPVs8'
    'Re{Ey^RHWF^%u?L~<rNh#5OSX?d#f#Mf#;$meNh+p@cXJ8GZm97Rkth>uNsq5=Bb+W%MrkftZC4Z?}@Nu^`0*RyTL#tS%yx$K}`='
    'k3>>N&UPb6cYJ3MlwpC-aAs$A$;Ea-1)M*SkAWx#15xr1_Ewp_Gd4xxw+~%_)WEHyPQO_kM$-'
    ')DI%RSjO=*e7Wx<%bHZ;NJN464N{sr7Lb8#!Xc-'
    '~i%&?EXJvZ82%<Um3^+g6>H={SIIJLi8%jg9Ny{y@=ASZxv8{wY@>3%=~?D;9?KHdIhjW$ZQqYRnEek2T?CZ5}HWQMJiv!iOb|EI'
    'g_p=PU`1E%GcJ)tWbG_HFrKtZ7CO;z0j;{K_o;a*oI+rhxzj8XZ5Y=|B4j|B++Ytkq}<G%e8RO;>%GJo1@ct=Am2Qb#=5$lp=vEl'
    'SJ7}O2|?fNI%Y&^7|o3?XAD5T-UNq~4;M(qxfC;_nH?6w<3>Wk$-aHK_NrGhiN?fLVNn{wCAJaP3l*|-^nL~@T*#-'
    'V;=vhetuE}P<qWWp5g1!_SUxP%oSH$kp65N#s?9>l50VY9+4fqsw}wsq1y0d&dd=D5}JC~X%2AEn^fjHt|ZEu;PcEj->Ie!4-'
    '#_M7TDkW&?Z&d1!TxZEZRWfPo+us!gS@O0CZlz?<;4%8#Bk7C8GWQ4G~)XwU5iDt|`p{2}vEe<R<U(XnJ6wn-T-EVF@qzQAhfj0@'
    '>pW7|n6yny7{)QMx2+>GcFKL=-'
    'C|cl?jO9jpI<1SP$hULP`XrDbE355xtG7|QUU`kthx=i(Da%C2v~;+6jQB}7L{#jw25fQ~VP?4<ijj?Te-o9YO8'
)


def dump(name: str, obj) -> None:
    (ROOT / name).write_text(json.dumps(obj, separators=(",", ":")))


def main() -> None:
    source = ROOT / "SET-1029-PRIMES.txt"
    if source.exists():
        raw = source.read_bytes()
    else:
        raw = zlib.decompress(base64.b85decode("".join(OFFICIAL_LIST_B85)))
        source.write_bytes(raw)
    digest = hashlib.sha256(raw).hexdigest()
    if digest != EXPECTED_SHA256:
        raise RuntimeError(f"official list SHA-256 mismatch: {digest}")
    primes = [int(x) for x in raw.split()]
    if len(primes) != 1029 or len(set(primes)) != 1029 or primes != sorted(primes):
        raise RuntimeError("official list does not contain 1029 sorted distinct integers")
    if not all(isprime(p) for p in primes):
        raise RuntimeError("a listed number failed primality testing")
    print("official list verified", len(primes), digest, flush=True)

    t0 = time.time()
    factors = []
    max_minus: dict[int, int] = {}
    max_plus: dict[int, int] = {}
    for i, p in enumerate(primes):
        fm = {int(q): int(e) for q, e in factorint(p - 1).items()}
        fp = {int(q): int(e) for q, e in factorint(p + 1).items()}
        factors.append({"p": p, "minus": fm, "plus": fp})
        for q, e in fm.items():
            max_minus[q] = max(max_minus.get(q, 0), e)
        for q, e in fp.items():
            max_plus[q] = max(max_plus.get(q, 0), e)
        if (i + 1) % 100 == 0:
            print("factored", i + 1, "elapsed", time.time() - t0, flush=True)
    dump("factors.json", factors)

    rows = []
    for sign, maxima in (("-", max_minus), ("+", max_plus)):
        for q, e in sorted(maxima.items()):
            if q == 2:
                if sign == "-" and e == 1:
                    continue
                if not (sign == "+" and e >= 3):
                    raise RuntimeError((sign, q, e))
                pe = 2**e
                order = 2 ** (e - 2)
                table = {pow(5, k, pe): k for k in range(order)}
                coeff = [table[(-p) % pe] for p in primes]
                rows.append({"name": f"{sign}2^{e}:log5", "m": order, "b": 0, "a": coeff})
                rows.append({"name": f"{sign}2^{e}:sign", "m": 2, "b": 1, "a": [1] * len(primes)})
            else:
                pe = q**e
                order = (q - 1) * q ** (e - 1)
                g = int(primitive_root(pe))
                table = {pow(g, k, pe): k for k in range(order)}
                coeff = [table[(p if sign == "-" else -p) % pe] for p in primes]
                target = 0
                common = math.gcd(order, target)
                for value in coeff:
                    common = math.gcd(common, value)
                if common > 1:
                    order //= common
                    target //= common
                    coeff = [value // common for value in coeff]
                rows.append({
                    "name": f"{sign}{q}^{e}", "q": q, "e": e,
                    "base_mod": pe, "g": g, "m": order, "b": target,
                    "a": coeff,
                })
        print("built", sign, "rows", len(rows), "elapsed", time.time() - t0, flush=True)
    if len(rows) != 120:
        raise RuntimeError(f"expected 120 global rows, got {len(rows)}")
    dump("global_rows.json", rows)

    split = []
    for j, row in enumerate(rows):
        for q, e in factorint(int(row["m"])).items():
            q, e = int(q), int(e)
            mod = q**e
            split.append({
                "parent": j,
                "name": row["name"] + f"|{q}^{e}",
                "p": q, "e": e, "m": mod,
                "b": int(row["b"]) % mod,
                "a": [int(a) % mod for a in row["a"]],
            })
    if len(split) != 313:
        raise RuntimeError(f"expected 313 split rows, got {len(split)}")
    dump("split_rows.json", split)

    # Row-reduce the common modulo-2 subsystem and generate reproducible hints.
    n = len(primes)
    matrix = []
    for row in rows:
        if int(row["m"]) % 2:
            continue
        bits = 0
        for i, a in enumerate(row["a"]):
            if int(a) & 1:
                bits |= 1 << i
        matrix.append(bits | ((int(row["b"]) & 1) << n))
    rank = 0
    pivots = []
    for c in range(n):
        k = next((i for i in range(rank, len(matrix)) if (matrix[i] >> c) & 1), None)
        if k is None:
            continue
        matrix[rank], matrix[k] = matrix[k], matrix[rank]
        for i in range(len(matrix)):
            if i != rank and ((matrix[i] >> c) & 1):
                matrix[i] ^= matrix[rank]
        pivots.append(c)
        rank += 1
        if rank == len(matrix):
            break
    if rank != 119:
        raise RuntimeError(f"expected GF(2) rank 119, got {rank}")
    pivot_set = set(pivots)
    free = [i for i in range(n) if i not in pivot_set]
    x0 = [0] * n
    for r, p in enumerate(pivots):
        x0[p] = (matrix[r] >> n) & 1
    moves = []
    for f in free:
        move = [f]
        for r, p in enumerate(pivots):
            if (matrix[r] >> f) & 1:
                move.append(p)
        moves.append(move)

    hints = []
    for seed in range(80):
        rng = random.Random(10000 + seed)
        x = x0[:]
        for move in moves:
            if rng.getrandbits(1):
                for i in move:
                    x[i] ^= 1
        hints.append({"name": f"xor_{seed}", "x": x})
    dump("hints.json", hints)

    summary = {
        "prime_count": len(primes),
        "prime_list_sha256": digest,
        "global_rows": len(rows),
        "split_rows": len(split),
        "xor_rank": rank,
        "free_variables": len(free),
        "log2_group_order": sum(math.log2(int(r["m"])) for r in rows),
        "expected_random_solution_exponent": len(primes) - sum(math.log2(int(r["m"])) for r in rows),
        "elapsed_seconds": time.time() - t0,
    }
    (ROOT / "model_summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
