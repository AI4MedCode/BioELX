import argparse
import os

class BioELXParser(argparse.ArgumentParser):
    def __init__(self, add_bioelx_args=True, add_model_args=False, description='BioELX parser'):
        super().__init__(
            description=description,
            allow_abbrev=False,
            conflict_handler='resolve',
            formatter_class=argparse.HelpFormatter,
            add_help=add_bioelx_args,
        )
        self.bioelx_home = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
        os.environ['BIOELX_HOME'] = self.bioelx_home
        self.add_arg = self.add_argument
        self.overridable = {}
        if add_bioelx_args:
            self.add_bioelx_args()
        if add_model_args:
            self.add_model_args()

    def add_bioelx_args(self, args=None):
        parser = self.add_argument_group("Common Arguments")
        parser.add_argument("--debug", action="store_true")
        parser.add_argument("--cuda", default="cuda:0", type=str)
        parser.add_argument("--top_k", default=10, type=int) 
        parser.add_argument("--baseline", default=None, type=str, required=False)

    def add_model_args(self, args=None):
        parser = self.add_argument_group("Model Arguments")
        parser.add_argument("--sapbert_model", type=str, default=None)
        parser.add_argument("--device", type=str, default="auto")
        parser.add_argument("--data_path", default="path-to-data", type=str)
        parser.add_argument("--kb_path", default="path-to-kb", type=str)
        parser.add_argument("--mention_path", type=str, default=None)
        parser.add_argument("--output_path", default='path-to-output-dir', type=str, required=True)
        parser.add_argument("--batch_size", type=int, default=32)
        parser.add_argument("--max_length", default=25, type=int)
        parser.add_argument("--language", default="en", type=str)
        parser.add_argument("--context", action="store_true")
        parser.add_argument("--force_reencode", action="store_true")
        parser.add_argument("--cache_dir", type=str, default=None)
        parser.add_argument("--kb_emb_path", type=str, default=None)
        parser.add_argument("--kb_meta_path", type=str, default=None)
        parser.add_argument("--mention_emb_path", type=str, default=None)
        parser.add_argument("--mention_meta_path", type=str, default=None)

    def add_kb_processing_args(self, args=None):
        parser = self.add_argument_group("KB Processing Arguments")
        parser.add_argument("--kb_path", type=str, required=True,
            help="Path to source KB file (e.g. UMLS MRCONSO.RRF).")
        parser.add_argument("--output_path", type=str, required=True,
            help="Output file path. Parent dir is created if missing.")
        parser.add_argument("--lowercase", action="store_true",
            help="Lowercase the name column. Default: keep original case (cased).")
        parser.add_argument("--dedup", action="store_true",
            help="Drop duplicate (cui, name) pairs. Default: keep duplicates.")

    def add_dataset_processing_args(self, args=None):
        parser = self.add_argument_group("Dataset Processing Arguments")
        parser.add_argument("--dataset", type=str, required=True,
            choices=["mantra", "medmentions", "wikimed-de"],
            help="Which annotated corpus to convert to xl-bel mention format.")
        parser.add_argument("--data_path", type=str, default=None,
            help="Source file or directory. Defaults to DATA_DIR/<dataset>.")
        parser.add_argument("--output_path", type=str, default=None,
            help="Output directory. Defaults to <data_path>/processed.")
        parser.add_argument("--splits", nargs="+", default=None,
            help="Subsets to write. mantra: EMEA/Medline/Patent (default all); "
                 "medmentions: train/dev/test (default all); "
                 "wikimed-de: train/test (default test).")

    def add_jina_args(self, args=None):
        parser = self.add_argument_group("Jina Reranker Arguments")
        parser.add_argument("--jina_model", default="jinaai/jina-reranker-v2-base-multilingual", type=str)
        parser.add_argument("--jina_max_length", default=1024, type=int)
        parser.add_argument("--score_batch_size", default=16, type=int)
        parser.add_argument("--only_mention", action="store_true")
        parser.add_argument("--short_context", action="store_true")
        parser.add_argument("--use_tgt", action="store_true",
            help="Wrap the mention with <tgt>...</tgt> in the query (Jina v3).")
        parser.add_argument("--jina_instruction", default=None, type=str,
            help="Override the task description used in the Qwen-style "
                 "'Instruct: ...\\nQuery: ...' prefix prepended to the query.")
        parser.add_argument("--use_jina_instruction", action="store_true",
            help="Prepend a Qwen-style 'Instruct: <task>\\nQuery: <query>' prefix "
                 "to the query text. Leaves the model's own prompt template alone.")

    def add_bge_args(self, args=None):
        parser = self.add_argument_group("BGE Reranker Arguments")
        parser.add_argument("--bge_model", default="BAAI/bge-reranker-v2-gemma", type=str)
        parser.add_argument("--bge_max_length", default=1024, type=int)
        parser.add_argument("--score_batch_size", default=16, type=int)
        parser.add_argument("--only_mention", action="store_true")
        parser.add_argument("--use_tgt", action="store_true",
            help="Wrap the mention with <tgt>...</tgt> in the query.")
        parser.add_argument("--bge_instruction", default=None, type=str,
            help="Instruction prepended to the query. If unset and "
                 "--use_bge_instruction is on, falls back to Qwen-style defaults. "
                 "Note: bge-reranker-v2-m3 is encoder-only and was not trained "
                 "on prompts; this is a query-text hack.")
        parser.add_argument("--use_bge_instruction", action="store_true",
            help="Enable prepending an instruction to the query text. "
                 "Off by default since BGE m3 was not trained on instructions.")

    def add_qwen_args(self, args=None):
        parser = self.add_argument_group("Qwen Reranker Arguments")
        parser.add_argument("--only_mention", action="store_true")
        parser.add_argument("--short_context", action="store_true")
        parser.add_argument("--model_size", default="0.6B", type=str)
        parser.add_argument("--qwen_max_length", default=8192, type=int)
        parser.add_argument("--score_batch_size", default=16, type=int)
        parser.add_argument("--print_input_shapes", action="store_true")
        parser.add_argument("--lora_path", default=None, type=str)
        parser.add_argument("--lora", action="store_true")
