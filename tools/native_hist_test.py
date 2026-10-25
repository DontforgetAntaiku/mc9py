
import mc9
from mc9 import cir as cirmod, library

mc9.config.engine = "native"
c = library.rc_lowpass().build("hist_t")
c.tolerance("R1", lot="10%")
c.monte_carlo(runs=40, seed=1, analysis="transient")
sec = cirmod.Section("Monte Carlo", ["Analysis=Transient", "Window Placement=2,3, -1,-1, -4,-25, 96,96,919,536",
        "Font=Height=-15,FStyle=0,Color=#0000FF,Name=Arial", "WinBackGround Color=#FFFFFF", "Select Color=#FF0000",
        "Select Box Color=#000080", "Title=Y_Level(v(out),1,1,10m)", "AutoTitle=Yes", "ShowWin=True", "BackGroundColor=#FFFFFF",
        "Grid Color=#808080", "Fore Color=#FFFFFF", "Shadow Color=#C0C0C0", "Auto=True", "Format=5",
        "PMExpression=Y_Level(v(out),1,1,10m)", ""])
i = c._cir._insert_point()
c._cir.sections.insert(i, sec)
c._dirty = True
r = c.transient(20e-3, 0, points=201, curves=["v(out)"])
print(r)
print(c.shot("hist_t_window.png", "window", trim=False))
c.close()
