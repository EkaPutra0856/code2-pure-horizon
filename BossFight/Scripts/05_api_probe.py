import unreal
c = unreal.AnimGraphLibrary
unreal.log("API AGL: " + ", ".join(m for m in dir(c) if not m.startswith("_") and m not in dir(unreal.Object)))
for p in ["/Game/Lucy/DEMO/Mannequin/Animations/ThirdPerson_AnimBP", "/Game/MageAnimationSet/DemoAssets/AnimBP/AnimationDemo_AnimBP"]:
    bp = unreal.load_asset(p)
    nodes = unreal.AnimationLibrary.get_nodes_of_class(bp, unreal.AnimGraphNode_Slot, True)
    unreal.log("SLOTS %s: %s" % (p, [n.get_editor_property("node").get_editor_property("slot_name") for n in nodes]))
    unreal.log("GRAPHS %s: %s" % (p, [g.get_name() for g in unreal.AnimationLibrary.get_animation_graphs(bp)]))
