from benchmark_fps import LaneModelWrapper


class CondLaneNetWrapper(LaneModelWrapper):
    def load_model(self):
        raise NotImplementedError("TODO: load CondLaneNet repo code and pretrained weights.")

    def infer(self, frame, frame_id=0, video_id="unknown"):
        raise NotImplementedError("TODO: return LaneFrameResult with polyline lanes.")
