from benchmark_fps import LaneModelWrapper


class UFLDWrapper(LaneModelWrapper):
    def load_model(self):
        raise NotImplementedError("TODO: load UFLD/UFLDv2 repo code and pretrained weights.")

    def infer(self, frame, frame_id=0, video_id="unknown"):
        raise NotImplementedError("TODO: return LaneFrameResult with polyline lanes.")
