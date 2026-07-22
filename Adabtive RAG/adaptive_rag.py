import os
import sys
import logging
import argparse
from typing import List, Dict, Any, Tuple, Optional
import tempfile
import json

# logging settings
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# check LangChain
try:
    import langchain
    LANGCHAIN_AVAILABLE = True
    logger.info("LangChain is available")
except ImportError:
    LANGCHAIN_AVAILABLE = False
    logger.warning("LangChain is not available, using fallback methods")

# ==================== RobustDocumentProcessor ====================

class RobustDocumentProcessor:
    """پردازشگر مستندات با قابلیت fallback برای فرمت‌های مختلف PDF"""
    
    def __init__(self, chunk_size=1000, chunk_overlap=200):
        """
        Initialize document processor
        
        Args:
            chunk_size (int): اندازه هر chunk متن
            chunk_overlap (int): میزان همپوشانی بین chunks
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.logger = logging.getLogger(__name__)
    
    def load_pdf(self, file_path):
        """بارگذاری PDF با روش‌های مختلف fallback"""
        self.logger.info(f"Loading PDF: {file_path}")
        
        # روش 1: PyPDF2
        try:
            import PyPDF2
            self.logger.info("Trying PyPDF2...")
            text = ""
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for page_num in range(len(pdf_reader.pages)):
                    page = pdf_reader.pages[page_num]
                    text += page.extract_text() + "\n"
            
            if text.strip():
                self.logger.info(f"PyPDF2 successful, extracted {len(text)} characters")
                return text
        except Exception as e:
            self.logger.warning(f"PyPDF2 failed: {e}")
        
        # روش 2: pdfminer.six (fallback)
        try:
            from pdfminer.high_level import extract_text
            self.logger.info("Trying pdfminer...")
            text = extract_text(file_path)
            if text.strip():
                self.logger.info(f"pdfminer successful, extracted {len(text)} characters")
                return text
        except Exception as e:
            self.logger.warning(f"pdfminer failed: {e}")
        
        # روش 3: خواندن ساده متن (آخرین راه‌حل)
        try:
            self.logger.info("Trying simple text reading...")
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as file:
                text = file.read()
            if text.strip():
                self.logger.info(f"Simple reading successful, extracted {len(text)} characters")
                return text
        except Exception as e:
            self.logger.error(f"All extraction methods failed: {e}")
        
        raise ValueError(f"Could not extract text from {file_path}")
    
    def split_text(self, text):
        """تقسیم متن به chunks"""
        self.logger.info(f"Splitting text of length {len(text)}")
        
        # اگر langchain_text_splitters یا langchain.text_splitter موجود باشد
        try:
            if LANGCHAIN_AVAILABLE:
                from langchain_text_splitters import RecursiveCharacterTextSplitter
                text_splitter = RecursiveCharacterTextSplitter(
                    chunk_size=self.chunk_size,
                    chunk_overlap=self.chunk_overlap,
                    length_function=len,
                    separators=["\n\n", "\n", " ", ""]
                )
                chunks = text_splitter.split_text(text)
                self.logger.info(f"LangChain splitter created {len(chunks)} chunks")
                return chunks
        except Exception as e:
            self.logger.warning(f"LangChain splitter failed, using simple splitter: {e}")
        
        # chunking
        chunks = []
        words = text.split()
        
        for i in range(0, len(words), self.chunk_size - self.chunk_overlap):
            chunk_words = words[i:i + self.chunk_size]
            chunk = ' '.join(chunk_words)
            chunks.append(chunk)
            
            if len(chunks) >= 1000:  # محدودیت برای جلوگیری از حافظه زیاد
                break
        
        self.logger.info(f"Simple splitter created {len(chunks)} chunks")
        return chunks
    
    def process_document(self, file_path):
        """پردازش کامل یک سند"""
        self.logger.info(f"Processing document: {file_path}")
        
        # استخراج متن
        text = self.load_pdf(file_path)
        
        # تقسیم به chunks
        chunks = self.split_text(text)
        
        # حذف duplicates
        unique_chunks = []
        seen = set()
        for chunk in chunks:
            chunk_hash = hash(chunk[:100])  # هش 100 کاراکتر اول
            if chunk_hash not in seen:
                seen.add(chunk_hash)
                unique_chunks.append(chunk)
        
        self.logger.info(f"Processed {len(unique_chunks)} unique chunks from {file_path}")
        return unique_chunks

# ==================== VectorStoreManager ====================

class VectorStoreManager:
    """مدیریت پایگاه داده برداری با ChromaDB"""
    
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.vector_store = None
        self.embeddings = None
        self._init_embeddings()
    
    def _init_embeddings(self):
        """بارگذاری مدل embeddings"""
        try:
            from sentence_transformers import SentenceTransformer
            self.logger.info(f"Loading embedding model: {self.config['embedding_model']}")
            self.embeddings = SentenceTransformer(self.config['embedding_model'])
            self.logger.info("Embedding model loaded successfully")
        except Exception as e:
            self.logger.error(f"Failed to load embedding model: {e}")
            raise
    
    def create_vector_store(self, documents: List[str]):
        """ایجاد پایگاه داده برداری"""
        try:
            import chromadb
            from chromadb.config import Settings
            
            self.logger.info(f"Creating ChromaDB collection: {self.config['collection_name']}")
            
            # ایجاد کلاینت ChromaDB
            client = chromadb.PersistentClient(
                path=self.config['persist_directory'],
                settings=Settings(allow_reset=True)
            )
            
            # حذف collection قبلی اگر وجود دارد
            try:
                client.delete_collection(self.config['collection_name'])
                self.logger.info(f"Deleted existing collection: {self.config['collection_name']}")
            except:
                pass
            
            # ایجاد collection جدید
            collection = client.create_collection(
                name=self.config['collection_name'],
                metadata={"hnsw:space": "cosine"}
            )
            
            # تولید embeddings و اضافه کردن به collection
            self.logger.info(f"Generating embeddings for {len(documents)} documents")
            
            batch_size = 32
            for i in range(0, len(documents), batch_size):
                batch_docs = documents[i:i + batch_size]
                batch_embeddings = self.embeddings.encode(batch_docs).tolist()
                
                # اضافه کردن به collection
                collection.add(
                    embeddings=batch_embeddings,
                    documents=batch_docs,
                    ids=[f"doc_{j}" for j in range(i, min(i + len(batch_docs), len(documents)))]
                )
            
            self.vector_store = collection
            self.logger.info(f"Vector store created with {len(documents)} documents")
            return collection
            
        except Exception as e:
            self.logger.error(f"Failed to create vector store: {e}")
            raise
    
    def similarity_search(self, query: str, top_k: int = None):
        """جستجوی مشابهت"""
        if top_k is None:
            top_k = self.config['similarity_top_k']
        
        if not self.vector_store:
            raise ValueError("Vector store not initialized")
        
        try:
            # تولید embedding برای query
            query_embedding = self.embeddings.encode([query]).tolist()[0]
            
            # جستجو در ChromaDB
            results = self.vector_store.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                include=["documents", "distances", "metadatas"]
            )
            
            documents = results['documents'][0] if results['documents'] else []
            distances = results['distances'][0] if results['distances'] else []
            
            # تبدیل distances به similarity scores
            similarities = [(1 - dist) for dist in distances] if distances else []
            
            return list(zip(documents, similarities))
            
        except Exception as e:
            self.logger.error(f"Similarity search failed: {e}")
            return []

# ==================== GapGPTClient ====================

class GapGPTClient:
    """کلاینت برای ارتباط با GapGPT API"""
    
    def __init__(self, api_key: str, base_url: str = None, model: str = None):
        self.api_key = api_key
        self.base_url = base_url or "https://api.gapgpt.app/v1"
        self.model = model or "gpt-4o-mini"
        self.logger = logging.getLogger(__name__)
    
    def generate(self, prompt: str, system_message: str = None, temperature: float = 0.1, max_tokens: int = 1000):
        """تولید پاسخ از GapGPT"""
        import requests
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        messages = []
        if system_message:
            messages.append({"role": "system", "content": system_message})
        messages.append({"role": "user", "content": prompt})
        
        data = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=data,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                return result['choices'][0]['message']['content']
            else:
                self.logger.error(f"GapGPT API error: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            self.logger.error(f"Failed to call GapGPT API: {e}")
            return None
    
    def classify_question(self, question: str):
        """طبقه‌بندی سوال به simple یا complex"""
        prompt = f"""
        سوال زیر را به عنوان "simple" یا "complex" طبقه‌بندی کن.
        
        سوال: {question}
        
        قوانین:
        - اگر سوال کوتاه باشد (کمتر از 6 کلمه) یا یک تعریف ساده بخواهد، "simple" است
        - اگر سوال نیاز به تحلیل، مقایسه، یا ترکیب چندین مفهوم داشته باشد، "complex" است
        - اگر سوال چند بخشی باشد یا نیاز به استدلال چند مرحله‌ای داشته باشد، "complex" است
        
        فقط پاسخ "simple" یا "complex" را برگردان.
        """
        
        response = self.generate(prompt, temperature=0)
        if response:
            response = response.strip().lower()
            if "simple" in response:
                return "simple"
            elif "complex" in response:
                return "complex"
        
        # default
        return "simple" if len(question.split()) < 6 else "complex"
    
    def expand_query(self, query: str):
        """گسترش query برای بهبود بازیابی"""
        prompt = f"""
        سوال زیر را برای بهبود بازیابی اطلاعات گسترش بده.
        معادل‌ها، مترادف‌ها، و مفاهیم مرتبط را اضافه کن.
        
        سوال اصلی: {query}
        
        سوال گسترش یافته را به زبان فارسی برگردان.
        """
        
        expanded = self.generate(prompt, temperature=0.3)
        return expanded or query
    
    def decompose_question(self, question: str):
        """تجزیه سوال پیچیده به زیرسوالات"""
        prompt = f"""
        سوال پیچیده زیر را به 2-4 زیرسوال ساده‌تر تجزیه کن.
        
        سوال اصلی: {question}
        
        زیرسوالات باید:
        1. مستقل باشند
        2. پاسخ‌های جداگانه داشته باشند
        3. در نهایت به پاسخ سوال اصلی کمک کنند
        
        زیرسوالات را به صورت لیست شماره‌دار برگردان.
        """
        
        decomposed = self.generate(prompt, temperature=0.2)
        if decomposed:
            # استخراج زیرسوالات از پاسخ
            lines = decomposed.strip().split('\n')
            subquestions = []
            for line in lines:
                line = line.strip()
                if line and (line[0].isdigit() or line.startswith('-') or line.startswith('*')):
                    # حذف شماره‌ها و علامت‌ها
                    clean_line = line.lstrip('0123456789.-* ')
                    if clean_line:
                        subquestions.append(clean_line)
            
            if subquestions:
                return subquestions
        
        # اگر تجزیه موفق نبود، سوال اصلی را برگردان
        return [question]

# ==================== Adaptive RAG System ====================

class AdaptiveRAGSystem:
    """سیستم Adaptive RAG اصلی"""
    
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # تنظیم API Key
        self.api_key = config.get('api_key')
        if not self.api_key:
            raise ValueError("API key is required for GapGPT")
        
        # ایجاد کامپوننت‌ها
        self.document_processor = RobustDocumentProcessor(
            chunk_size=config['chunk_size'],
            chunk_overlap=config['chunk_overlap']
        )
        self.vector_manager = VectorStoreManager(config)
        self.gapgpt_client = GapGPTClient(
            api_key=self.api_key,
            base_url=config['gapgpt_base_url'],
            model=config['gapgpt_model']
        )
        
        self.vector_store_initialized = False
        self.logger.info("Adaptive RAG System initialized")
    
    def process_documents(self, pdf_paths: List[str]):
        """پردازش اسناد و ایجاد vector store"""
        all_chunks = []
        
        for pdf_path in pdf_paths:
            self.logger.info(f"Processing document: {pdf_path}")
            chunks = self.document_processor.process_document(pdf_path)
            all_chunks.extend(chunks)
        
        self.logger.info(f"Total chunks: {len(all_chunks)}")
        
        # ایجاد vector store
        self.vector_manager.create_vector_store(all_chunks)
        self.vector_store_initialized = True
        
        return len(all_chunks)
    
    def simple_rag(self, question: str):
        """RAG ساده برای سوالات ساده"""
        self.logger.info(f"Running simple RAG for: {question}")
        
        # اگر سوال کوتاه است، آن را گسترش بده
        if len(question.split()) < 6:
            self.logger.info("Short question detected, expanding query...")
            expanded_query = self.gapgpt_client.expand_query(question)
            self.logger.info(f"Expanded query: {expanded_query}")
            retrieved_docs = self.vector_manager.similarity_search(expanded_query)
        else:
            retrieved_docs = self.vector_manager.similarity_search(question)
        
        if not retrieved_docs:
            self.logger.warning("No documents retrieved")
            return "متأسفانه، در ارتباط با مدل زبانی مورد نظر، پاسخی برای سوال شما پیدا نشد."
        
        # ساخت context
        context = "\n\n".join([doc[0] for doc in retrieved_docs[:3]])
        
        # ساخت prompt
        prompt = f"""
        بر اساس context زیر به سوال پاسخ بده.
        
        Context:
        {context}
        
        سوال: {question}
        
        پاسخ را به زبان فارسی و به صورت واضح و مختصر ارائه کن.
        اگر پاسخ در context وجود ندارد، بگو "پاسخ در اسناد موجود یافت نشد."
        """
        
        # تولید پاسخ
        answer = self.gapgpt_client.generate(
            prompt,
            system_message="شما یک دستیار هوشمند هستید که بر اساس اسناد ارائه شده پاسخ می‌دهید.",
            temperature=self.config['temperature'],
            max_tokens=self.config['max_tokens']
        )
        
        return answer or "پاسخی تولید نشد."
    
    def decomposed_rag(self, question: str):
        """RAG تجزیه شده برای سوالات پیچیده"""
        self.logger.info(f"Running decomposed RAG for: {question}")
        
        # تجزیه سوال
        subquestions = self.gapgpt_client.decompose_question(question)
        self.logger.info(f"Decomposed into {len(subquestions)} subquestions")
        
        answers = []
        for i, subq in enumerate(subquestions, 1):
            self.logger.info(f"Processing subquestion {i}/{len(subquestions)}: {subq}")
            
            # بازیابی برای هر زیرسوال
            retrieved_docs = self.vector_manager.similarity_search(subq)
            if retrieved_docs:
                context = "\n\n".join([doc[0] for doc in retrieved_docs[:2]])
                
                prompt = f"""
                بر اساس context زیر به سوال پاسخ بده.
                
                Context:
                {context}
                
                سوال: {subq}
                
                پاسخ را به صورت مختصر و به زبان فارسی ارائه کن.
                """
                
                # اصلاح: temperature نباید منفی باشد
                temp = max(0.0, self.config['temperature'] * 0.5)  # نصف دما اما مثبت
                answer = self.gapgpt_client.generate(
                    prompt,
                    temperature=temp,
                    max_tokens=500
                )
                
                if answer:
                    answers.append(f"{i}. {subq}\n   پاسخ: {answer}")
            else:
                answers.append(f"{i}. {subq}\n   پاسخ: اطلاعات کافی یافت نشد")
        
        # ترکیب پاسخ‌ها
        combined_answers = "\n\n".join(answers)
        
        prompt = f"""
        بر اساس پاسخ‌های جزئی زیر، به سوال اصلی پاسخ جامع بده.
        
        سوال اصلی: {question}
        
        پاسخ‌های جزئی:
        {combined_answers}
        
        یک پاسخ جامع و یکپارچه به زبان فارسی ارائه کن که تمام جنبه‌های سوال را پوشش دهد.
        """
        
        final_answer = self.gapgpt_client.generate(
            prompt,
            system_message="شما یک تحلیل‌گر متخصص هستید که پاسخ‌های جزئی را ترکیب می‌کنید.",
            temperature=self.config['temperature'],
            max_tokens=self.config['max_tokens']
        )
        
        return final_answer or "پاسخی تولید نشد."
    
    def hyde_rag(self, question: str):
        """HyDE (Hypothetical Document Embeddings)"""
        self.logger.info(f"Running HyDE RAG for: {question}")
        
        # تولید پاسخ فرضی
        prompt = f"""
        یک پاسخ فرضی به سوال زیر بنویس.
        این پاسخ باید شبیه به متنی باشد که در اسناد مرتبط یافت می‌شود.
        
        سوال: {question}
        
        پاسخ فرضی را به زبان فارسی و به صورت یک پاراگراف بنویس.
        """
        
        hypothetical_answer = self.gapgpt_client.generate(
            prompt,
            temperature=0.3,
            max_tokens=500
        )
        
        if hypothetical_answer:
            # استفاده از پاسخ فرضی برای بازیابی
            retrieved_docs = self.vector_manager.similarity_search(hypothetical_answer)
            
            if retrieved_docs:
                context = "\n\n".join([doc[0] for doc in retrieved_docs[:3]])
                
                prompt = f"""
                بر اساس context زیر به سوال پاسخ بده.
                
                Context:
                {context}
                
                سوال: {question}
                
                پاسخ را به زبان فارسی و به صورت واضح ارائه کن.
                """
                
                answer = self.gapgpt_client.generate(
                    prompt,
                    system_message="شما یک دستیار هوشمند هستید که بر اساس اسناد ارائه شده پاسخ می‌دهید.",
                    temperature=self.config['temperature'],
                    max_tokens=self.config['max_tokens']
                )
                
                return answer or "پاسخی تولید نشد."
        
        # fallback به simple RAG
        return self.simple_rag(question)
    
    def adaptive_query(self, question: str):
        """پرس‌وجوی تطبیقی با انتخاب خودکار بهترین روش"""
        if not self.vector_store_initialized:
            raise ValueError("Vector store not initialized. Process documents first.")
        
        # طبقه‌بندی سوال
        question_type = self.gapgpt_client.classify_question(question)
        self.logger.info(f"Question classified as: {question_type}")
        
        if question_type == "simple":
            self.logger.info("Using simple RAG path")
            # ابتدا simple RAG را امتحان کن
            answer = self.simple_rag(question)
            
            # اگر پاسخ مناسب نبود، به HyDE برو
            if "پیدا نشد" in answer or "یافت نشد" in answer:
                self.logger.info("Simple RAG failed, trying HyDE")
                answer = self.hyde_rag(question)
        
        else:  # complex
            self.logger.info("Using complex RAG path")
            # ابتدا decomposed RAG را امتحان کن
            answer = self.decomposed_rag(question)
            
            # اگر پاسخ مناسب نبود، به HyDE برو
            if "پیدا نشد" in answer or "یافت نشد" in answer or len(answer) < 100:
                self.logger.info("Decomposed RAG may be insufficient, trying HyDE")
                answer = self.hyde_rag(question)
        
        return answer
    
    def adaptive_query_with_details(self, question: str):
        """نسخه پیشرفته adaptive_query که جزئیات فرآیند را برمی‌گرداند"""
        if not self.vector_store_initialized:
            raise ValueError("Vector store not initialized. Process documents first.")
        
        details = {
            "question": question,
            "question_type": None,
            "method_used": None,
            "answer": None,
            "subquestions": [],
            "retrieved_docs_count": 0
        }
        
        # طبقه‌بندی سوال
        question_type = self.gapgpt_client.classify_question(question)
        details["question_type"] = question_type
        
        if question_type == "simple":
            details["method_used"] = "simple_rag"
            answer = self.simple_rag(question)
            
            if "پیدا نشد" in answer or "یافت نشد" in answer:
                details["method_used"] = "hyde_rag"
                answer = self.hyde_rag(question)
        
        else:  # complex
            details["method_used"] = "decomposed_rag"
            answer = self.decomposed_rag(question)
            
            if "پیدا نشد" in answer or "یافت نشد" in answer or len(answer) < 100:
                details["method_used"] = "hyde_rag"
                answer = self.hyde_rag(question)
        
        details["answer"] = answer
        return details
    
    def get_system_info(self):
        """دریافت اطلاعات سیستم"""
        return {
            "vector_store_initialized": self.vector_store_initialized,
            "chunk_size": self.config['chunk_size'],
            "chunk_overlap": self.config['chunk_overlap'],
            "embedding_model": self.config['embedding_model'],
            "gapgpt_model": self.config['gapgpt_model'],
            "similarity_top_k": self.config['similarity_top_k'],
            "temperature": self.config['temperature'],
            "max_tokens": self.config['max_tokens']
        }

# ==================== Configuration ====================

DEFAULT_CONFIG = {
    'chunk_size': 1000,
    'chunk_overlap': 200,
    'similarity_top_k': 5,
    'temperature': 0.1,
    'max_tokens': 1000,
    'collection_name': "adaptive_rag_docs",
    'persist_directory': "./chroma_db",
    'embedding_model': "paraphrase-multilingual-MiniLM-L12-v2",
    'gapgpt_base_url': "https://api.gapgpt.app/v1",
    'gapgpt_model': "gpt-4o-mini"
}

# ==================== Main Function ====================

def main():
    parser = argparse.ArgumentParser(description='Adaptive RAG System')
    parser.add_argument('--api-key', required=True, help='GapGPT API Key')
    parser.add_argument('--pdf', required=True, help='PDF file path')
    parser.add_argument('--question', help='Question to ask')
    parser.add_argument('--test-all', action='store_true', help='Test all question types')
    
    args = parser.parse_args()
    
    # تنظیم config
    config = DEFAULT_CONFIG.copy()
    config['api_key'] = args.api_key
    
    # ایجاد سیستم
    system = AdaptiveRAGSystem(config)
    
    # پردازش اسناد
    print(f"Processing PDF: {args.pdf}")
    num_chunks = system.process_documents([args.pdf])
    print(f"Processed {num_chunks} chunks")
    
    if args.test_all:
        # تست انواع سوالات
        test_questions = [
            ("ساده", "مدل زبانی بزرگ (LLM) چیست؟"),
            ("کوتاه", "LLM مخفف چیست؟"),
            ("پیچیده", "مدل‌های BERT و GPT را از نظر معماری و کاربرد مقایسه کنید.")
        ]
        
        for q_type, question in test_questions:
            print(f"\n{'='*50}")
            print(f"Testing {q_type} question: {question}")
            print(f"{'='*50}")
            
            answer = system.adaptive_query(question)
            print(f"Answer:\n{answer}")
    
    elif args.question:
        # پاسخ به سوال خاص
        print(f"\nQuestion: {args.question}")
        answer = system.adaptive_query(args.question)
        print(f"\nAnswer:\n{answer}")
    
    else:
        print("Please provide either --question or --test-all")

if __name__ == "__main__":
    main()
